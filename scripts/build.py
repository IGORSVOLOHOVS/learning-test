import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTENT_DIR = os.path.join(HERE, "content")
TESTS_DIR = os.path.join(ROOT, "tests")
TEMPLATE_PATH = os.path.join(HERE, "template.html")

# slug -> display title
TOPICS = {
    "probability_statistics": "Вероятность и статистика",
    "linear_algebra": "Линейная алгебра (матрицы, SVD)",
    "calculus": "Математический анализ (производные, цепное правило)",
    "computer_vision": "Основы Computer Vision",
    "world_models": "Теория World Models",
    "diffusers": "Библиотека diffusers (Python/ML)",
    "python_numpy_matplotlib": "Практика Python (NumPy и Matplotlib)",
    "physical_chemistry": "Физическая химия",
    "electronics": "Основы электроники",
    "facial_emotion_recognition": "Распознавание эмоций человека по лицу",
    "first_impression": "Техники первого впечатления",
    "pragmatics_model": "Двухэтапная модель прагматика",
    "photography_exposure": "Выдержка в фотографии и её контекст",
    "network_drivers": "Сетевые драйверы",
    "low_level_cpp": "Низкоуровневый C++",
    "assembly": "Ассемблер",
    "performance_optimization": "Оптимизация производительности",
    "iso_standards": "ISO стандарты (менеджмент и ИТ)",
    "tiktok_algorithm": "TikTok: алгоритмы рекомендаций",
    "visual_math": "Визуальное объяснение математических концепций",
}


def build_one(slug, title, template):
    content_path = os.path.join(CONTENT_DIR, slug + ".json")
    with open(content_path, encoding="utf-8") as f:
        questions = json.load(f)
    if len(questions) != 50:
        raise ValueError(f"{slug}: expected 50 questions, got {len(questions)}")
    for i, q in enumerate(questions):
        if len(q["options"]) != 4:
            raise ValueError(f"{slug} q{i}: expected 4 options")
        if not (0 <= q["correct"] <= 3):
            raise ValueError(f"{slug} q{i}: correct index out of range")

    html = template.replace("__TITLE__", title)
    html = html.replace("__TEST_ID__", slug)
    html = html.replace("__QUESTIONS_JSON__", json.dumps(questions, ensure_ascii=False))

    out_path = os.path.join(TESTS_DIR, slug + ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path, len(questions)


def main():
    os.makedirs(TESTS_DIR, exist_ok=True)
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    built = []
    missing = []
    for slug, title in TOPICS.items():
        content_path = os.path.join(CONTENT_DIR, slug + ".json")
        if not os.path.exists(content_path):
            missing.append(slug)
            continue
        out_path, n = build_one(slug, title, template)
        built.append((slug, title, n))
        print(f"OK  {slug} -> {out_path} ({n} questions)")

    if missing:
        print("\nMissing content files (skipped):")
        for m in missing:
            print(" -", m)

    print(f"\nBuilt {len(built)}/{len(TOPICS)} tests.")


if __name__ == "__main__":
    main()
