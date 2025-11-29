from llama_cpp import Llama

# Initialize the model with verbose=False to disable logs
llm = Llama(
    model_path="/home/abhi/Pictures/DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf",
    n_ctx=2048,
    n_threads=4,
    chat_format="chatml",  # Use appropriate chat format
    verbose=False  # Disable logs
)

# Start a conversation
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum computing in simple terms."}
]

# Create chat completion with streaming enabled
response_stream = llm.create_chat_completion(
    messages=messages,
    max_tokens=256,
    stream=True  # Enable streaming
)

# Process the streaming response
full_response = ""
print("Assistant: ", end="", flush=True)

for chunk in response_stream:
    delta = chunk['choices'][0]['delta']
    if 'content' in delta:
        content = delta['content']
        print(content, end="", flush=True)
        full_response += content

print()  # Add a newline at the end
