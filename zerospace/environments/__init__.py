from zerospace.environments.base import BaseEnvironment
from zerospace.environments.multi import MultiLanguageEnvironment, LANGUAGE_HANDLERS

def get_environment_handler(language: str) -> BaseEnvironment:
    """Returns the environment handler instance for the specified language(s)."""
    if not language:
        return MultiLanguageEnvironment(["python"])
        
    # Split comma-separated list of languages
    languages = [lang.strip().lower() for lang in language.split(",") if lang.strip()]
    if not languages:
        languages = ["python"]
        
    return MultiLanguageEnvironment(languages)

