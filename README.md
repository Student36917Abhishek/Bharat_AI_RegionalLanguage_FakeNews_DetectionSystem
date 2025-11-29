

# 🔍 The Bharat: Regional Language Fake News Detection System

![Bharat Logo](https://github.com/Student36917Abhishek/Bharat_AI_RegionalLanguage_FakeNews_DetectionSystem/blob/main/images/logo.png)

## Overview

The Bharat: Regional Language Fact News Detection System is designed as an agentic, self-learning AI pipeline that continuously scans Indian media and social platforms in real-time — detecting fake or misleading content before it spreads.

We didn't build just another classifier — we built a system that understands context, thinks logically, and verifies facts step-by-step using trusted national sources.

It starts from a simple idea:

"What if a single AI could read India's 22 languages, understand a claim, and verify it — all without needing millions of samples?"

That's exactly what Bharat does. It uses few-shot multilingual fine-tuning (MuRIL style) so the model learns faster with less data — and still captures language-specific tone, emotion, and misinformation patterns.

## Features

- **Multilingual Support**: Processes content in all 22 official Indian languages
- **Reddit Integration**: Scrapes relevant discussions from Reddit
- **Automatic Translation**: Translates regional language content to English for analysis
- **AI-Powered Claim Detection**: Identifies potential claims using advanced AI
- **Fact-Checking**: Verifies claims against trusted news sources
- **Classification System**: Categorizes claims as TRUE, FALSE, or UNVERIFIABLE
- **Web Search Integration**: Enables custom web search for additional verification
- **Interactive Dashboard**: User-friendly Streamlit interface

## Repository Structure

```
Bharat_AI_RegionalLanguage_FakeNews_DetectionSystem/
├── app.py                 # Main Streamlit web application
├── main2.py               # Command-line interface
├── extract_data.py         # Data extraction module
├── translate_data.py       # Translation module
├── main3.py               # Claims generation module
├── fact_check.py           # Fact-checking module
├── main5.py               # LLM classification module
├── reddit.py              # Reddit scraping module
├── custom_results/         # Output directory for results
├── models/                # Model files
│   └── DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf
└── requirements.txt        # Python dependencies
```

## Installation

### Prerequisites

- Python 3.8+
- Git
- NVIDIA GPU with CUDA support (recommended for optimal performance)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Student36917Abhishek/Bharat_AI_RegionalLanguage_FakeNews_DetectionSystem.git
cd Bharat_AI_RegionalLanguage_FakeNews_DetectionSystem
```

### Step 2: Create a Virtual Environment

```bash
# Create virtual environment
python -m venv bharat_env

# Activate virtual environment
# On Linux/Mac:
source bharat_env/bin/activate
# On Windows:
bharat_env\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Download Required Models

The system requires a language model for classification. Download the model file:

```bash
# Create models directory if it doesn't exist
mkdir -p models

# Download the model (this might take some time)
# Note: DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf from hugging face
```

### Step 5: Configure API Keys

Add the api keys respective  file in the root directory .





### Step 6: Create Output Directory

Create a directory where results will be stored:

```bash
mkdir -p custom_results
```

## Configuration

### Reddit API Configuration

To enable Reddit scraping, you need to create a Reddit app:

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in the required fields:
   - Name: Bharat Fake News Detection
   - Select "script"
   - About URL: http://localhost:8501
4. Note down the client ID and client secret

### Google API Configuration

For translation and query refinement, you need a Google API key:

1. Go to Google Cloud Console (https://console.cloud.google.com/)
2. Create a new project
3. Enable the "Cloud Translation API" and "Generative Language API"
4. Create credentials (API key)
5. Add the API key to your `.env` file

## Running the Application

### Method 1: Streamlit Web Application (Recommended)

```bash
streamlit run app.py
```

This will start the web interface at `http://localhost:8501`

### Method 2: Command Line Interface

```bash
python main2.py
```

This runs the system in command-line mode with predefined parameters.




2. Add your search API keys to the configuration file

3. Restart the application for changes to take effect

## Project Workflow

1. **Search Query Input**: Enter a topic to search on Reddit
2. **AI Query Refinement**: The system refines your query using AI
3. **Data Scraping**: Scrapes relevant Reddit posts and discussions
4. **Data Extraction**: Extracts key information from the scraped data
5. **Translation**: Translates regional language content to English
6. **Claim Generation**: Identifies potential claims from the translated content
7. **Fact-Checking**: Verifies claims against trusted news sources
8. **AI Classification**: Classifies claims as TRUE, FALSE, or UNVERIFIABLE
9. **Results Display**: Presents findings in an easy-to-understand format

## Output Files

The system generates several output files in the `custom_results/` directory:

- `verified_claims.json`: Claims extracted from Reddit discussions
- `fact_check_results.json`: Results of the fact-checking process
- `fact_check_classification_results.json`: Final classification with AI reasoning

## Troubleshooting

### Common Issues

1. **Reddit API Errors**:
   - Verify your Reddit API credentials in the `.env` file
   - Check if your Reddit app has the correct permissions

2. **Translation Errors**:
   - Ensure your Google API key has the Translation API enabled
   - Check if you've exceeded your API quota

3. **Model Loading Errors**:
   - Verify the model file exists in the `models/` directory
   - Ensure you have sufficient RAM/VRAM for the model

4. **Web Search Errors**:
   - Check your search API configuration
   - Verify API keys are correctly set

### Performance Optimization

1. **GPU Acceleration**:
   - Install CUDA-compatible PyTorch: `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118`
   - Ensure NVIDIA drivers are up to date

2. **Memory Management**:PI keys are correctly se
   - Reduce batch sizes if running out of memory
   - Close unnecessary applications while running the system

## Contributing

We welcome contributions to improve Bharat. We also acknowledge the valuable contributions from the community, including work by [Prathamesh](https://github.com/Prathameshsci369).

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use Bharat in your research or work, please cite:

```bibtex
@misc{bharat2025,
  title={Bharat: Regional Language Fake News Detection System},
  author={Abhishek Patil  and Prathamesh Anand}
  year={2025},
  publisher={GitHub Repository},
  howpublished={\url{https://github.com/Student36917Abhishek/Bharat_AI_RegionalLanguage_FakeNews_DetectionSystem}}
}
```

## Contact

For questions, suggestions, or collaborations:

- Email: abhishekpatil.36917@gmail.com
- GitHub Issues: https://github.com/Student36917Abhishek/Bharat_AI_RegionalLanguage_FakeNews_DetectionSystem/issues
- GitHub (Prathamesh): https://github.com/Prathameshsci369

---

*An Indian-made, multilingual truth engine — smart, adaptive, and built for real impact.*
