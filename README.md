# Teaching Monster: Baseline & Starter Kit!

## Prerequisite to Run the Baseline
* Gemini API: visit [the website](https://aistudio.google.com/welcome) to get your API Key, and in `config/.env`, insert:
   ```
   GEMINI_API_KEY={YOUR_OWN_API_KEY}
   ```
* Server: An GPU w/ 20GB VRAM is recommended.

## Environment Setup

* This project uses **Python 3.10**, and needs libreoffice & poppler to be installed. The installation subjects to the OS.

* Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Run the pipeline locally!
```bash
python -m scripts.T2V_pipeline \
  -r "REQUIREMENT_PROMPT" \
  -p "PERSONA_PROMPT" \
  [-c config/default.yaml] \
  [-o final_video.mp4] \
  [-d ./output]
```