/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface Window {
  SpeechRecognition?: new () => any;
  webkitSpeechRecognition?: new () => any;
}
