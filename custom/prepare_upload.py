#!/usr/bin/env python3
import json, os


def create_meta_json(project_dir):
    title = input("Title (optional): ").strip()
    year = input("Year (required): ").strip()
    doc_type = input(
        "Type [Training regulation/Curriculum/Systematic listing/Job profile/Other VET document]: "
    ).strip()

    if not year.isdigit():
        print("Year must be a number.")
        return

    meta = {
        "title": title if title else None,
        "year": int(year),
        "type": doc_type if doc_type else "Other VET document",
    }

    meta_path = os.path.join(project_dir, ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"Created {meta_path}.")

if __name__ == "__main__":
    project_dir = input("Enter OCR4All project directory: ").strip()
    if not os.path.isdir(project_dir):
        print("Directory not found.")
    else:
        create_meta_json(project_dir)
