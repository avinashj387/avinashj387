"""Tests for videogen.

The spec/timeline/filtergraph layers are pure functions over data, so they are
tested with stubbed probes and no ffmpeg. The final test does render a real
file, and skips itself when ffmpeg is not installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from videogen import graph, manifest, timeline  # noqa: E402
from videogen.ffmpeg import MediaInfo, Tools  # noqa: E402
from videogen.manifest import Spec, SpecError  # noqa: E402

STILL = MediaInfo("still.jpg", has_video=True, has_audio=False,
                  width=1600, height=1200, duration=None)
MOVIE = MediaInfo("movie.mp4", has_video=True, has_audio=True,
                  width=1920, height=1080, duration=10.0)
VOICE = MediaInfo("vo.wav", has_video=False, has_audio=True,
                  width=None, height=None, duration=3.0)


def fake_probe(mapping: dict[str, MediaInfo]):
    def _probe(_tools, path):
        return mapping[os.path.basename(path)]
    return _probe


def resolve(spec: Spec, mapping: dict[str, MediaInfo]) -> timeline.Timeline:
    with mock.patch.object(timeline, "probe", fake_probe(mapping)):
        return timeline.resolve(spec, Tools("ffmpeg", "ffprobe"))


class SpecParsing(unittest.TestCase):
    def test_clip_shorthand_is_a_path_string(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg"]})
        self.assertEqual(len(spec.clips), 2)
        self.assertTrue(spec.clips[0].path.endswith("a.jpg"))

    def test_rejects_empty_clip_list(self):
        with self.assertRaisesRegex(SpecError, "non-empty list"):
            Spec.parse({"clips": []})

    def test_misspelled_field_names_the_valid_ones(self):
        with self.assertRaisesRegex(SpecError, r"unknown field\(s\) durtion"):
            Spec.parse({"clips": [{"path": "a.jpg", "durtion": 3}]})

    def test_rejects_odd_dimensions(self):
        with self.assertRaisesRegex(SpecError, "even"):
            Spec.parse({"clips": ["a.jpg"], "width": 1919, "height": 1080})

    def test_rejects_unknown_motion(self):
        with self.assertRaisesRegex(SpecError, "spec.clips\\[0\\].motion"):
            Spec.parse({"clips": [{"path": "a.jpg", "motion": "spin"}]})

    def test_duration_accepts_only_numbers_or_auto(self):
        Spec.parse({"clips": [{"path": "a.jpg", "duration": "auto"}]})
        with self.assertRaisesRegex(SpecError, "number or 'auto'"):
            Spec.parse({"clips": [{"path": "a.jpg", "duration": "soon"}]})

    def test_top_level_caption_is_style_only(self):
        # No "text" here: the top-level block styles the per-clip captions.
        spec = Spec.parse({"clips": ["a.jpg"], "caption": {"size": 30}})
        self.assertEqual(spec.defaults.caption.size, 30)

    def test_clip_caption_requires_text(self):
        with self.assertRaisesRegex(SpecError, "non-empty"):
            Spec.parse({"clips": [{"path": "a.jpg", "caption": {"size": 30}}]})

    def test_clip_caption_inherits_top_level_styling(self):
        spec = Spec.parse({
            "clips": [{"path": "a.jpg", "caption": "hello"}],
            "caption": {"size": 72, "color": "yellow", "position": "top"},
        })
        caption = spec.clips[0].caption
        self.assertEqual((caption.text, caption.size, caption.color,
                          caption.position), ("hello", 72, "yellow", "top"))

    def test_relative_paths_resolve_against_the_spec_file(self):
        spec = Spec.parse({"clips": ["photos/a.jpg"]}, base_dir="/srv/project")
        self.assertEqual(spec.clips[0].path, "/srv/project/photos/a.jpg")

    def test_transition_string_shorthand(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg"], "transition": "wipeleft"})
        self.assertEqual(spec.defaults.transition.type, "wipeleft")

    def test_transition_none_zeroes_its_duration(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg"],
                           "transition": {"type": "none", "duration": 2}})
        self.assertFalse(spec.defaults.transition.active)

    def test_random_motion_is_stable_for_a_given_seed(self):
        def motions(seed):
            spec = Spec.parse({"clips": ["a.jpg", "b.jpg", "c.jpg"], "seed": seed})
            return [spec.resolve_motion(c, i) for i, c in enumerate(spec.clips)]
        self.assertEqual(motions(5), motions(5))
        self.assertNotEqual(motions(5), motions(6))


class TimelineMath(unittest.TestCase):
    def test_crossfades_overlap_so_total_is_shorter_than_the_sum(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg", "c.jpg"], "duration": 4,
                           "transition": {"type": "fade", "duration": 0.5}})
        result = resolve(spec, {"a.jpg": STILL, "b.jpg": STILL, "c.jpg": STILL})
        self.assertAlmostEqual(result.total, 4 * 3 - 0.5 * 2)
        self.assertAlmostEqual(result.clips[1].start, 3.5)
        self.assertAlmostEqual(result.clips[2].start, 7.0)

    def test_hard_cuts_do_not_overlap(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg"], "duration": 4,
                           "transition": "none"})
        result = resolve(spec, {"a.jpg": STILL, "b.jpg": STILL})
        self.assertAlmostEqual(result.total, 8.0)
        self.assertAlmostEqual(result.clips[1].start, 4.0)

    def test_mixed_transitions_accumulate_correctly(self):
        spec = Spec.parse({"clips": [
            {"path": "a.jpg", "transition": "none"},
            {"path": "b.jpg", "transition": {"type": "fade", "duration": 1.0}},
            {"path": "c.jpg"},
        ], "duration": 3})
        result = resolve(spec, {"a.jpg": STILL, "b.jpg": STILL, "c.jpg": STILL})
        self.assertAlmostEqual(result.clips[1].start, 3.0)   # hard cut
        self.assertAlmostEqual(result.clips[2].start, 5.0)   # 1s crossfade
        self.assertAlmostEqual(result.total, 8.0)

    def test_transition_is_clamped_to_the_shorter_neighbour(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg"], "duration": 1,
                           "transition": {"type": "fade", "duration": 5}})
        result = resolve(spec, {"a.jpg": STILL, "b.jpg": STILL})
        self.assertAlmostEqual(
            timeline.transition_duration(spec, result.clips, 0), 0.9)
        self.assertTrue(any("too long" in note for note in result.warnings))

    def test_auto_duration_follows_the_narration(self):
        spec = Spec.parse({"clips": [
            {"path": "a.jpg", "duration": "auto", "narration": "vo.wav"}]})
        result = resolve(spec, {"a.jpg": STILL, "vo.wav": VOICE})
        self.assertAlmostEqual(result.total, 3.0 + timeline.NARRATION_TAIL)

    def test_auto_duration_follows_a_video_clip_length(self):
        spec = Spec.parse({"clips": [{"path": "movie.mp4", "duration": "auto"}]})
        result = resolve(spec, {"movie.mp4": MOVIE})
        self.assertAlmostEqual(result.total, 10.0)

    def test_auto_duration_on_a_bare_still_warns_and_falls_back(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "duration": "auto"}]})
        result = resolve(spec, {"a.jpg": STILL})
        self.assertAlmostEqual(result.total, timeline.FALLBACK_DURATION)
        self.assertTrue(any("falling back" in note for note in result.warnings))

    def test_duration_is_capped_by_what_remains_after_start(self):
        spec = Spec.parse({"clips": [
            {"path": "movie.mp4", "start": 8, "duration": 5}]})
        result = resolve(spec, {"movie.mp4": MOVIE})
        self.assertAlmostEqual(result.total, 2.0)
        self.assertTrue(any("only" in note for note in result.warnings))

    def test_start_past_the_end_is_an_error(self):
        spec = Spec.parse({"clips": [{"path": "movie.mp4", "start": 99}]})
        with self.assertRaisesRegex(SpecError, "past the end"):
            resolve(spec, {"movie.mp4": MOVIE})

    def test_narration_without_audio_is_an_error(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "narration": "b.jpg"}]})
        with self.assertRaisesRegex(SpecError, "no audio stream"):
            resolve(spec, {"a.jpg": STILL, "b.jpg": STILL})

    def test_audio_only_input_as_a_clip_is_an_error(self):
        spec = Spec.parse({"clips": ["vo.wav"]})
        with self.assertRaisesRegex(SpecError, "no video/image stream"):
            resolve(spec, {"vo.wav": VOICE})

    def test_input_indices_are_unique_across_clips_narration_and_music(self):
        spec = Spec.parse({
            "clips": [{"path": "a.jpg", "narration": "vo.wav"}, "movie.mp4"],
            "music": "music.mp3",
        })
        result = resolve(spec, {"a.jpg": STILL, "movie.mp4": MOVIE,
                                "vo.wav": VOICE})
        indices = [c.input_index for c in result.clips]
        indices += [c.narration_input_index for c in result.clips
                    if c.narration_input_index is not None]
        indices.append(result.music_input_index)
        self.assertEqual(sorted(indices), list(range(len(indices))))


class Filtergraph(unittest.TestCase):
    def build(self, spec: Spec, mapping: dict[str, MediaInfo]) -> graph.Command:
        result = resolve(spec, mapping)
        self.workdir = tempfile.mkdtemp(prefix="videogen-test-")
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        return graph.build(result, self.workdir)

    def test_xfade_offset_equals_the_next_clip_start(self):
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg", "c.jpg"], "duration": 4,
                           "transition": {"type": "fade", "duration": 0.5}})
        command = self.build(spec, {"a.jpg": STILL, "b.jpg": STILL, "c.jpg": STILL})
        self.assertIn("offset=3.5000", command.filtergraph)
        self.assertIn("offset=7.0000", command.filtergraph)

    def test_hard_cut_uses_concat_and_pins_the_timebase(self):
        # concat and fps emit different timebases; xfade refuses to join those,
        # so every link must be normalised to AVTB.
        spec = Spec.parse({"clips": ["a.jpg", "b.jpg"], "transition": "none"})
        command = self.build(spec, {"a.jpg": STILL, "b.jpg": STILL})
        self.assertIn("concat=n=2:v=1:a=0,settb=AVTB", command.filtergraph)
        self.assertEqual(command.filtergraph.count("settb=AVTB"), 3)

    def test_stills_get_zoompan_and_videos_do_not(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "motion": "zoom-in"},
                                     "movie.mp4"]})
        command = self.build(spec, {"a.jpg": STILL, "movie.mp4": MOVIE})
        chains = command.filtergraph.split(";\n")
        self.assertIn("zoompan", chains[0])
        self.assertNotIn("zoompan", chains[1])

    def test_motion_none_skips_supersampling(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "motion": "none"}],
                           "width": 1280, "height": 720})
        command = self.build(spec, {"a.jpg": STILL})
        self.assertIn("scale=1280:720", command.filtergraph)
        self.assertNotIn("zoompan", command.filtergraph)

    def test_pan_expressions_move_in_opposite_directions(self):
        def expression(motion):
            spec = Spec.parse({"clips": [{"path": "a.jpg", "motion": motion}]})
            return self.build(spec, {"a.jpg": STILL}).filtergraph
        self.assertIn("x='(iw-iw/zoom)*(on/119)'", expression("pan-right"))
        self.assertIn("x='(iw-iw/zoom)*(1-(on/119))'", expression("pan-left"))

    def test_zoom_in_and_out_are_inverses(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "motion": "zoom-in"},
                                     {"path": "b.jpg", "motion": "zoom-out"}],
                           "zoom": 1.5})
        text = self.build(spec, {"a.jpg": STILL, "b.jpg": STILL}).filtergraph
        self.assertIn("z='1+0.500000*(on/119)'", text)
        self.assertIn("z='1.500000-0.500000*(on/119)'", text)

    def test_letterboxing_never_distorts_the_source(self):
        spec = Spec.parse({"clips": ["movie.mp4"], "background": "0x101820"})
        text = self.build(spec, {"movie.mp4": MOVIE}).filtergraph
        self.assertIn("force_original_aspect_ratio=decrease", text)
        self.assertIn("color=0x101820", text)

    def test_caption_text_goes_to_a_sidecar_file(self):
        # Colons and quotes in the text would otherwise break the filtergraph.
        tricky = "Chapter 1: it's 50% done, really"
        spec = Spec.parse({"clips": [{"path": "a.jpg", "caption": tricky}]})
        text = self.build(spec, {"a.jpg": STILL}).filtergraph
        self.assertIn("textfile=", text)
        self.assertNotIn(tricky, text)
        with open(os.path.join(self.workdir, "caption_0.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), tricky)

    def test_caption_positions_map_to_y_expressions(self):
        def y_for(position):
            spec = Spec.parse({"clips": [{"path": "a.jpg", "caption": {
                "text": "x", "position": position, "margin": 40}}]})
            return self.build(spec, {"a.jpg": STILL}).filtergraph
        self.assertIn("y=40:", y_for("top"))
        self.assertIn("y=(h-text_h)/2:", y_for("center"))
        self.assertIn("y=h-text_h-40:", y_for("bottom"))

    def test_narration_is_delayed_to_its_clip_start(self):
        spec = Spec.parse({"clips": [
            {"path": "a.jpg", "duration": 4},
            {"path": "b.jpg", "duration": 4, "narration": "vo.wav"},
        ], "transition": "none"})
        text = self.build(spec, {"a.jpg": STILL, "b.jpg": STILL,
                                 "vo.wav": VOICE}).filtergraph
        self.assertIn("adelay=4000:all=1", text)

    def test_first_clip_narration_is_not_delayed(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "narration": "vo.wav"}]})
        text = self.build(spec, {"a.jpg": STILL, "vo.wav": VOICE}).filtergraph
        self.assertNotIn("adelay", text)

    def test_ducking_is_wired_only_when_voices_and_music_coexist(self):
        base = {"clips": [{"path": "a.jpg", "narration": "vo.wav"}]}
        mapping = {"a.jpg": STILL, "vo.wav": VOICE}

        with_music = self.build(Spec.parse({**base, "music": "m.mp3"}), mapping)
        self.assertIn("sidechaincompress", with_music.filtergraph)

        no_music = self.build(Spec.parse(base), mapping)
        self.assertNotIn("sidechaincompress", no_music.filtergraph)

        no_voice = self.build(
            Spec.parse({"clips": ["a.jpg"], "music": "m.mp3"}), {"a.jpg": STILL})
        self.assertNotIn("sidechaincompress", no_voice.filtergraph)

    def test_ducking_can_be_turned_off(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "narration": "vo.wav"}],
                           "music": {"path": "m.mp3", "duck": False}})
        text = self.build(spec, {"a.jpg": STILL, "vo.wav": VOICE}).filtergraph
        self.assertNotIn("sidechaincompress", text)
        self.assertIn("amix", text)

    def test_silent_project_produces_no_audio_stream(self):
        spec = Spec.parse({"clips": ["a.jpg"]})
        command = self.build(spec, {"a.jpg": STILL})
        self.assertIsNone(command.audio_label)

    def test_a_video_clips_own_audio_is_kept(self):
        spec = Spec.parse({"clips": [{"path": "movie.mp4", "volume": 0.5}]})
        command = self.build(spec, {"movie.mp4": MOVIE})
        self.assertIsNotNone(command.audio_label)
        self.assertIn("volume=0.5000", command.filtergraph)

    def test_music_fades_land_at_the_end_of_the_timeline(self):
        spec = Spec.parse({"clips": ["a.jpg"], "duration": 10,
                           "music": {"path": "m.mp3", "fade_out": 2}})
        text = self.build(spec, {"a.jpg": STILL}).filtergraph
        self.assertIn("afade=t=out:st=8.0000:d=2.0000", text)

    def test_looping_music_uses_stream_loop(self):
        spec = Spec.parse({"clips": ["a.jpg"],
                           "music": {"path": "m.mp3", "loop": True}})
        command = self.build(spec, {"a.jpg": STILL})
        self.assertIn("-stream_loop", command.inputs)

    def test_stills_are_looped_for_their_full_duration(self):
        spec = Spec.parse({"clips": [{"path": "a.jpg", "duration": 3}]})
        command = self.build(spec, {"a.jpg": STILL})
        self.assertIn("-loop", command.inputs)
        self.assertIn("3.0000", command.inputs)


class PathEscaping(unittest.TestCase):
    def test_windows_style_paths_are_escaped_for_the_filtergraph(self):
        self.assertEqual(graph.escape_path(r"C:\fonts\arial.ttf"),
                         r"C\:/fonts/arial.ttf")

    def test_quotes_are_escaped(self):
        self.assertEqual(graph.escape_path("/home/o'brien/a.ttf"),
                         r"/home/o\'brien/a.ttf")


class DirectoryScan(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="videogen-scan-")
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)

    def touch(self, *names):
        for name in names:
            open(os.path.join(self.directory, name), "w").close()

    def test_media_is_ordered_by_filename_and_other_files_ignored(self):
        self.touch("02.jpg", "01.png", "03.mp4", "notes.txt", ".hidden.jpg")
        spec = manifest.from_directory(self.directory)
        self.assertEqual([os.path.basename(c.path) for c in spec.clips],
                         ["01.png", "02.jpg", "03.mp4"])

    def test_empty_directory_explains_what_it_looked_for(self):
        self.touch("readme.txt")
        with self.assertRaisesRegex(SpecError, "no images or videos"):
            manifest.from_directory(self.directory)


@unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg not installed")
class EndToEnd(unittest.TestCase):
    """Renders a real file, and checks ffprobe agrees with the plan."""

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="videogen-e2e-")
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.directory, name)

    def make_image(self, name, size="640x480"):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"testsrc2=size={size}:duration=1:rate=1",
             "-frames:v", "1", self.path(name)], check=True)

    def make_audio(self, name, seconds=2):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"sine=frequency=440:duration={seconds}",
             self.path(name)], check=True)

    def probe_duration(self, path):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
        return float(out.stdout.strip())

    def test_renders_stills_captions_and_audio_to_the_planned_duration(self):
        self.make_image("a.jpg", "800x600")
        self.make_image("b.jpg", "600x800")   # different aspect: exercises padding
        self.make_audio("vo.wav", 2)
        spec = Spec.parse({
            "width": 320, "height": 240, "fps": 24, "seed": 1,
            "transition": {"type": "fade", "duration": 0.5},
            "clips": [
                {"path": "a.jpg", "duration": 2, "caption": "It's 50%: done",
                 "motion": "zoom-in"},
                {"path": "b.jpg", "duration": "auto", "narration": "vo.wav",
                 "motion": "pan-left"},
            ],
            "music": {"path": "vo.wav", "volume": 0.2},
        }, base_dir=self.directory)

        from videogen.build import render
        output = self.path("out.mp4")
        result = render(spec, output, quality="fast", quiet=True)

        # 2 + (2 + 0.5 tail) - 0.5 crossfade
        self.assertAlmostEqual(result.duration, 4.0, places=3)
        self.assertAlmostEqual(self.probe_duration(output), 4.0, places=1)

        streams = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height", "-of", "csv=p=0", output],
            capture_output=True, text=True, check=True).stdout
        self.assertIn("video,320,240", streams)
        self.assertIn("audio", streams)

    def test_dry_run_writes_nothing(self):
        self.make_image("a.jpg")
        spec = Spec.parse({"clips": ["a.jpg"], "width": 320, "height": 240},
                          base_dir=self.directory)
        from videogen.build import render
        output = self.path("nothing.mp4")
        render(spec, output, quiet=True, dry_run=True)
        self.assertFalse(os.path.exists(output))


if __name__ == "__main__":
    unittest.main(verbosity=2)
