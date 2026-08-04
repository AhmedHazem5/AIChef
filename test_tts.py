from audio.text_to_speech import TextToSpeech


print("Creating TTS service...")

tts = TextToSpeech()

print("Testing first sentence...")
tts.speak(
    "Hello Ahmed. I am Chef AI."
)

print("Testing second sentence...")
tts.speak(
    "My voice model remained loaded between both sentences."
)

print("TTS test complete.")