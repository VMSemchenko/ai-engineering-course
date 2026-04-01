from langchain_text_splitters import RecursiveCharacterTextSplitter

large_document = """
Artificial intelligence has transformed how businesses operate across every industry.
Machine learning models now power recommendation systems, fraud detection, and autonomous vehicles.
The key challenge remains data quality — models are only as good as the data they're trained on.

Natural language processing has seen remarkable progress with transformer architectures.
Large language models can now generate text, translate languages, and answer complex questions.
However, these models require massive computational resources and carefully curated training data.

Computer vision applications range from medical imaging to autonomous navigation.
Convolutional neural networks can detect tumors in X-rays with accuracy matching radiologists.
Real-time object detection enables self-driving cars to navigate complex urban environments.

Reinforcement learning has achieved superhuman performance in games like Go and StarCraft.
These algorithms learn optimal strategies through trial and error in simulated environments.
Transfer learning allows models trained in simulation to adapt to real-world conditions.

The ethical implications of AI deployment require careful consideration.
Bias in training data can lead to discriminatory outcomes in hiring and lending decisions.
Transparency and explainability are essential for building trust in AI systems.
""".strip()

print(f"Document: {len(large_document)} chars\n")
print("=" * 60)

for chunk_size in [100, 200, 500]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=20,
    )
    chunks = splitter.split_text(large_document)

    print(f"\nchunk_size={chunk_size} -> {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        preview = chunk[:60].replace("\n", " ")
        print(f"  [{i}] ({len(chunk):>3} chars) {preview}...")
