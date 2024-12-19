from transformers import pipeline

# Load GPT-2 model (do this only once to save loading time)
generator = pipeline('text-generation', model='gpt2')

def get_suggestion(input_text, max_new_tokens=20, temperature=0.5, top_p=0.9):
    """Generate a suggestion based on the input text."""
    try:
        output = generator(
            input_text, 
            max_new_tokens=max_new_tokens,
            num_return_sequences=1,
            temperature=temperature,
            top_p=top_p
        )
        # Extract the generated text and return it
        generated_text = output[0]['generated_text'].strip()
        return generated_text
    except Exception as e:
        print(f"Error generating suggestion: {e}")
        return None
