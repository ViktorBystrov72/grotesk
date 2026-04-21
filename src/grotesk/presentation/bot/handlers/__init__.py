from grotesk.presentation.bot.handlers.auth import setup_auth_handlers
from grotesk.presentation.bot.handlers.balance import setup_balance_handlers
from grotesk.presentation.bot.handlers.history import setup_history_handlers
from grotesk.presentation.bot.handlers.predict import setup_predict_handlers


def setup_all_handlers(dp) -> None:
    setup_auth_handlers(dp)
    setup_balance_handlers(dp)
    setup_predict_handlers(dp)
    setup_history_handlers(dp)
