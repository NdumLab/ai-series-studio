import {
  Wand2,
  Image as ImageIcon,
  Video,
  Music2,
  Mic2,
  Save,
} from "lucide-react";

export const STAGES = [
  { value: "story", label: "Story" },
  { value: "scenes", label: "Scenes" },
  { value: "characters", label: "Characters" },
  { value: "images", label: "Images" },
  { value: "segments", label: "Video Segments" },
  { value: "voice-music", label: "Voice / Music" },
  { value: "export", label: "Export" },
];

export const WALLET_STATE_COLOR = {
  normal: "#34C759",
  warning: "#FFCC00",
  high: "#FF9500",
  insufficient: "#FF3B30",
};

export const PROVIDER_SECTIONS = [
  { key: "llm", label: "LLM (Story rewrite)", icon: Wand2 },
  { key: "image", label: "Image", icon: ImageIcon },
  { key: "video", label: "Video", icon: Video },
  { key: "voice", label: "Voice", icon: Mic2 },
  { key: "music", label: "Music", icon: Music2 },
  { key: "export", label: "Export", icon: Save },
];

export const VOICE_PROVIDER_OPTIONS = [
  { id: "elevenlabs", label: "ElevenLabs" },
  { id: "openai-tts", label: "OpenAI TTS" },
  { id: "google-tts", label: "Google Cloud TTS" },
  { id: "custom", label: "Custom voice provider" },
];
