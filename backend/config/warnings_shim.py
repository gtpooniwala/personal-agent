import warnings


def configure_warnings():
    """
    Configure global warning filters for the application.

    This function should be called at the application entry point to handle
    known upstream warnings that are safe to ignore.
    """
    # LangChain 1.2.x imports a compatibility shim that emits this warning on Python 3.14.
    # Keep this narrowly scoped to the known upstream message.
    warnings.filterwarnings(
        "ignore",
        message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
        category=UserWarning,
        module=r"langchain_core\._api\.deprecation",
    )
