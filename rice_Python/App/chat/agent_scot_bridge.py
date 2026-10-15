from pathlib import Path
import sys
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = PROJECT_ROOT / "experiment"

load_dotenv(PROJECT_ROOT / ".env", override=True)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from agent_scot import generate_response_scot
from .language_adapter import adapt_answer_language, normalize_language
from .question_adapter import normalize_question_for_agent


def generate_response(user_input: str, session_id: str, method: str = "s_cot_raps", language: str = "en") -> str:
    agent_input = normalize_question_for_agent(user_input)
    answer, _tokens = generate_response_scot(
        agent_input,
        session_id,
        method=method,
        use_got_ci=True,
    )
    return adapt_answer_language(answer, user_input, normalize_language(language))
