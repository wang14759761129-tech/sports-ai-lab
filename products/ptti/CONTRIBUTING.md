# Working together

Owner and Kaikai review annotation meaning together. Keep main usable; feature/* for functionality, fix/* for bugs (Codex-created branches may use codex/*). Run pytest and the frontend build before review. Include a screenshot and reproducible match when changing the dashboard. Never commit private training data without consent, secrets, local databases, virtualenvs or generated builds. Label synthetic data. Preserve recovered research files and document migration mappings before adapting their schema.

Start with README setup steps. Current tests use temporary databases, never the personal match library. Add domain tests for new metrics and scoring cases. Submit small changes with the problem, resulting behavior and validation evidence.
