from backend.db import Base, engine, ensure_vector_extension
from scripts import generate_synthetic, generate_task_pool, seed


def main() -> None:
    ensure_vector_extension(engine)
    Base.metadata.create_all(bind=engine)
    seed.seed_concepts()
    seed.seed_contexts()
    generate_task_pool.generate_pool()
    generate_synthetic.main()


if __name__ == "__main__":
    main()
