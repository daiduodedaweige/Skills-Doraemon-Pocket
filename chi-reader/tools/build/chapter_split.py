import os
import re
import argparse
import fitz  # PyMuPDF


def is_target_title(title: str) -> bool:
    """
    只匹配下面三种目录标题前缀：
    - AX.X
    - BX.X
    - CX.X

    例如：
    A1.2 xxx        -> 匹配
    B3.4.5 xxx      -> 匹配
    C2.1 xxx        -> 匹配

    例如：
    A1.2.3 xxx      -> 不匹配
    B1.2.3.4 xxx    -> 不匹配
    C1.2.3 xxx      -> 不匹配
    """
    title = title.strip()

    patterns = [
        r"^A\d+\.\d+(?!\.)\b",       # A1.2
        r"^B\d+\.\d+(?!\.)\b",       # B1.2 
        r"^C\d+\.\d+(?!\.)\b",       # C1.2
    ]

    return any(re.match(pattern, title) for pattern in patterns)


def safe_filename(name: str) -> str:
    """
    清理文件名中的非法字符，避免保存失败
    """
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Split the CHI architecture PDF into section PDFs.")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    parser.add_argument(
        "--input",
        default=os.path.join(project_root, "source", "IHI0050H_amba_chi_architecture_spec.pdf"),
        help="Source CHI PDF path.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(project_root, "artifacts", "split_pdfs"),
        help="Directory for generated section PDFs.",
    )
    args = parser.parse_args()

    doc = fitz.open(args.input)
    toc = doc.get_toc()  # [level, title, page]

    # 只保留目标章节
    target_toc = [(level, title, page) for level, title, page in toc if is_target_title(title)]

    os.makedirs(args.output_dir, exist_ok=True)

    # 切分并导出
    for i in range(len(target_toc)):
        _, title, start_page = target_toc[i]
        end_page = target_toc[i + 1][2] - 1 if i + 1 < len(target_toc) else doc.page_count

        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_page - 1, to_page=end_page - 1)

        output_path = os.path.join(args.output_dir, f"{safe_filename(title)}.pdf")
        new_doc.save(output_path)
        new_doc.close()

    doc.close()


if __name__ == "__main__":
    main()
