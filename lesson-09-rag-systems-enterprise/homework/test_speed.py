import time
from sentence_transformers import SentenceTransformer
import torch

def test(device):
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device=device)
    docs = ["Hello world, this is a test document to see how fast we can embed things."] * 512
    
    t0 = time.time()
    model.encode(docs, batch_size=512)
    t1 = time.time()
    print(f"Device: {device}, Time for 512 docs: {t1-t0:.2f}s")

if __name__ == "__main__":
    test("cpu")
    if torch.backends.mps.is_available():
        test("mps")
