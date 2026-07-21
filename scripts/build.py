import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTENT_DIR = os.path.join(HERE, "content")
TESTS_DIR = os.path.join(ROOT, "tests")
TEMPLATE_PATH = os.path.join(HERE, "template.html")

# slug -> {title, sim: optional sim slug (same as topic slug) if a sims/*.html exists for it}
TOPICS = {
    "probability_statistics": {"title": "Вероятность и статистика", "sim": "probability_statistics"},
    "linear_algebra": {"title": "Линейная алгебра (матрицы, SVD)", "sim": "linear_algebra"},
    "calculus": {"title": "Математический анализ (производные, цепное правило)", "sim": "calculus"},
    "computer_vision": {"title": "Основы Computer Vision", "sim": "computer_vision"},
    "world_models": {"title": "Теория World Models", "sim": "world_models"},
    "diffusers": {"title": "Библиотека diffusers (Python/ML)", "sim": "diffusers"},
    "python_numpy_matplotlib": {"title": "Практика Python (NumPy и Matplotlib)", "sim": "python_numpy_matplotlib"},
    "physical_chemistry": {"title": "Физическая химия", "sim": "physical_chemistry"},
    "electronics": {"title": "Основы электроники", "sim": "electronics"},
    "facial_emotion_recognition": {"title": "Распознавание эмоций человека по лицу", "sim": "facial_emotion_recognition"},
    "first_impression": {"title": "Техники первого впечатления", "sim": "first_impression"},
    "pragmatics_model": {"title": "Двухэтапная модель прагматика", "sim": "pragmatics_model"},
    "photography_exposure": {"title": "Выдержка в фотографии и её контекст", "sim": "photography_exposure"},
    "network_drivers": {"title": "Сетевые драйверы", "sim": "network_drivers"},
    "low_level_cpp": {"title": "Низкоуровневый C++", "sim": "low_level_cpp"},
    "assembly": {"title": "Ассемблер", "sim": "assembly"},
    "performance_optimization": {"title": "Оптимизация производительности", "sim": "performance_optimization"},
    "iso_standards": {"title": "ISO стандарты (менеджмент и ИТ)", "sim": "iso_standards"},
    "tiktok_algorithm": {"title": "TikTok: алгоритмы рекомендаций", "sim": "tiktok_algorithm"},
    "visual_math": {"title": "Визуальное объяснение математических концепций", "sim": "visual_math"},
    "cpu_pipeline": {"title": "Конвейер команд и параллелизм (ILP)", "sim": ""},
}


def build_one(slug, title, sim, template):
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

    if sim:
        sim_link_html = f'<a class="iconbtn" href="../sims/{sim}.html">🔬 Лаборатория</a>'
    else:
        sim_link_html = ""

    html = template.replace("__TITLE__", title)
    html = html.replace("__TEST_ID__", slug)
    html = html.replace("__SIM_LINK__", sim_link_html)
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
    for slug, meta in TOPICS.items():
        content_path = os.path.join(CONTENT_DIR, slug + ".json")
        if not os.path.exists(content_path):
            missing.append(slug)
            continue
        out_path, n = build_one(slug, meta["title"], meta["sim"], template)
        built.append((slug, meta["title"], n))
        sim_note = f" [+lab: {meta['sim']}]" if meta["sim"] else ""
        print(f"OK  {slug} -> {out_path} ({n} questions){sim_note}")

    if missing:
        print("\nMissing content files (skipped):")
        for m in missing:
            print(" -", m)

    print(f"\nBuilt {len(built)}/{len(TOPICS)} tests.")


if __name__ == "__main__":
    main()
