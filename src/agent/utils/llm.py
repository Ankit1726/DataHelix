from langchain_groq import ChatGroq
from langchain_core.rate_limiters import InMemoryRateLimiter
from dotenv import load_dotenv

load_dotenv()

# Groq's documented replacement for the retired Llama 3.1 8B Instant model.
model = ChatGroq(
    model="openai/gpt-oss-20b",
    max_retries=5,
    rate_limiter=InMemoryRateLimiter(
        requests_per_second=0.4,
        check_every_n_seconds=0.1,
        max_bucket_size=1,
    ),
    streaming=True,
)