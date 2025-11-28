"""
Update file paths to work with Docker volume mounts
Run this script before building the Docker image
"""

import os

def update_file_paths():
    """Update all file paths in Python files to use current directory"""
    
    files_to_update = [
        'extract_data.py',
        'main2.py', 
        'main3.py',
        'main4.py',
        'main5.py',
        'translate_data.py'
    ]
    
    path_mappings = {
        # Original absolute paths → Docker volume paths
        '/home/anand/Bharat_fake_new/reddit_data56498.json': './reddit_data56498.json',
        '/home/abhi/Downloads/DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf': './DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf',
        '/home/abhi/Downloads/DeepSeek-R1-Distill-Qwen-1.5B-Q8_0.gguf': './DeepSeek-R1-Distill-Qwen-1.5B-Q8_0.gguf',
        
        # Output files
        'extracted_reddit_data.json': './extracted_reddit_data.json',
        'translated_reddit_data.json': './translated_reddit_data.json', 
        'claims_extracted.json': './claims_extracted.json',
        'valid_claims_with_queries.json': './valid_claims_with_queries.json',
        'verified_claims.json': './verified_claims.json'
    }
    
    for filename in files_to_update:
        if os.path.exists(filename):
            print(f"Updating paths in {filename}...")
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace paths
            for old_path, new_path in path_mappings.items():
                content = content.replace(old_path, new_path)
            
            # Write back
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Updated {filename}")
        else:
            print(f"⚠️  File not found: {filename}")

if __name__ == "__main__":
    update_file_paths()
    print("🎯 All file paths updated for Docker!")
    print("📝 Note: Large files will be accessed via volume mount")
