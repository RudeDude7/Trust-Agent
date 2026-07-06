import os
from exa_py import Exa
from dotenv import load_dotenv
load_dotenv()
try:
    exa = Exa(os.environ["EXA_API_KEY"])
    exa.search_and_contents("test", type="neural", use_autoprompt=True, num_results=3, text=True, start_published_date="invalid_date")
except Exception as e:
    print(str(e))
