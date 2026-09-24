import { useCallback, useEffect, useRef, useState } from "react";

export interface AudioEngine {
  playing: boolean;
  currentTime: number;
  duration: number | null;
  ready: boolean;
  error: string | null;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (t: number) => void;
  skip: (delta: number) => void;
}

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

/**
 * Single source of truth for the playhead: wraps one HTMLAudioElement and reports
 * currentTime via requestAnimationFrame while playing (timeupdate alone is ~4 Hz and
 * reads as a stuttering timeline). The timeline, transport and transcript all read it.
 */
export function useAudioEngine(src: string | null): AudioEngine {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCurrentTime(0);
    setPlaying(false);
    setDuration(null);
    setReady(false);
    setError(null);
    if (!src) return;

    const el = new Audio();
    el.preload = "metadata";
    el.src = src;
    audioRef.current = el;

    let raf: number | null = null;
    const stopRaf = () => {
      if (raf !== null) {
        cancelAnimationFrame(raf);
        raf = null;
      }
    };
    const tick = () => {
      setCurrentTime(el.currentTime);
      raf = requestAnimationFrame(tick);
    };

    const onMeta = () => {
      if (Number.isFinite(el.duration) && el.duration > 0) setDuration(el.duration);
      setReady(true);
    };
    const onPlay = () => {
      setPlaying(true);
      stopRaf();
      raf = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      stopRaf();
      setCurrentTime(el.currentTime);
    };
    const onEnded = () => {
      setPlaying(false);
      stopRaf();
      setCurrentTime(el.duration || 0);
    };
    const onError = () => {
      setPlaying(false);
      stopRaf();
      setError("audio playback failed — the file could not be loaded");
    };
    const onTime = () => {
      if (el.paused) setCurrentTime(el.currentTime);
    };

    el.addEventListener("loadedmetadata", onMeta);
    el.addEventListener("durationchange", onMeta);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("ended", onEnded);
    el.addEventListener("error", onError);
    el.addEventListener("timeupdate", onTime);

    return () => {
      stopRaf();
      el.removeEventListener("loadedmetadata", onMeta);
      el.removeEventListener("durationchange", onMeta);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("ended", onEnded);
      el.removeEventListener("error", onError);
      el.removeEventListener("timeupdate", onTime);
      el.pause();
      el.removeAttribute("src");
      audioRef.current = null;
    };
  }, [src]);

  const play = useCallback(() => {
    audioRef.current?.play().catch(() => setError("playback was blocked — press play again"));
  }, []);
  const pause = useCallback(() => audioRef.current?.pause(), []);
  const toggle = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) void el.play().catch(() => setError("playback was blocked — press play again"));
    else el.pause();
  }, []);
  const seek = useCallback((t: number) => {
    const el = audioRef.current;
    if (!el) return;
    const target = clamp(t, 0, Number.isFinite(el.duration) && el.duration > 0 ? el.duration : t);
    el.currentTime = target;
    setCurrentTime(target);
  }, []);
  const skip = useCallback(
    (delta: number) => {
      const el = audioRef.current;
      if (el) seek(el.currentTime + delta);
    },
    [seek],
  );

  return { playing, currentTime, duration, ready, error, play, pause, toggle, seek, skip };
}
