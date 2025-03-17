import logging

def configure_logging(verbose: bool):
    level = logging.INFO if verbose else logging.ERROR
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    # File handler
    file_handler = logging.FileHandler('diff.log')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Console handler 
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
