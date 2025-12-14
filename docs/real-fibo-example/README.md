# Real Bria FIBO Render Evidence

This folder contains a validated live render produced with the Bria inference engine (FIBO model).

Files:
- `structured_prompt.json` — schema-aligned structured prompt used for generation
- `backend_bria_request.json` — request sent to this project’s `/render/shot/sync`
- `backend_bria_response.json` — response with the real hosted image URL
- `explain.json` — deterministic explainability output from `/shots/{id}/explain`
- `output.png` — downloaded render
- `output_thumb.png` — thumbnail for quick viewing

Demo note:
The main demo defaults to the mock provider for speed and reliability.
This folder proves live Bria FIBO integration.
