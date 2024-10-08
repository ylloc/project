import dataclasses
import os
import re
import typing

import nbformat


@dataclasses.dataclass
class Cell:
    is_changed: bool  # изменена ли ячейка по сравнению с оригиналом (или является новой)
    cell_type: str  # 'markdown' или 'code'
    cell_text: str

    def __iter__(self):
        return iter((self.is_changed, self.cell_type, self.cell_text))


def get_filenames_from_directory(path_dir: str) -> typing.List[str]:
    out = []
    for file in os.listdir(os.fsencode(path_dir)):
        filename = os.fsdecode(file)
        if filename.endswith(".ipynb"):
            out.append(os.path.join(path_dir, filename))
    return out


# Достает из ноутбука все ячейки, выкидывая ненужные (картинки/прочие вложения).
def get_filtered_notebook_cells_from_dir(path_dir: str) -> typing.List[Cell]:
    cells = []
    with open(path_dir, 'r', encoding='utf-8') as file:
        notebook = nbformat.read(file, as_version=4)
        for cell in notebook.cells:
            if cell.cell_type == 'code':
                cells.append(Cell(False, 'code', cell.source))
            elif cell.cell_type == 'markdown':
                if 'attachments' not in cell and 'base64' not in cell.source:
                    cells.append(Cell(False, 'markdown', cell.source))
    return cells


# Сравнивает пустую и сделанную работы. Добавляет пометки(Cell.is_changed=true) в сделанной работе на ячейки, которые
# поменял студент, при этом объединяя подряд идущие одинакового типа ('code'/'text')
def mark_modified_cells(original_cells: typing.List[Cell],
                        modified_cells: typing.List[Cell]) -> typing.List[Cell]:
    original_content = set(cell.cell_text for cell in original_cells)

    for cell in modified_cells:
        if cell.cell_text not in original_content:
            cell.is_changed = True

    return modified_cells


# Принимает на вход список ячеек(Cell). Разбивает на задания, то есть на выходе список длины равной количеству заданий.
# Expected_task_count задается вызывающей стороной, если не найдется столько заданий бросает исключение.
def parse_and_mark_cells_by_tasks(cells: typing.List[Cell], expected_task_count: int) \
        -> typing.List[typing.List[Cell]]:
    tasks = [[] for _ in range(expected_task_count)]
    current_task_index = -1

    for cell in cells:
        # Bullshit проверка, на всякий случай на будущее. Надо переделать
        match = re.search(r"##\s*([Зз])адача\s*(\d+)", cell.cell_text)
        if match:
            task_number = int(match.group(2))
            if 1 <= task_number <= expected_task_count:
                current_task_index = task_number - 1
                tasks[current_task_index].append(cell)
                continue
            else:
                raise RuntimeError(f"{task_number} > {EXPECTED_TASKS}")

        # Стоит наверное еще добавить все что перед первой задачей к контексту первой задачи.
        if current_task_index != -1:
            tasks[current_task_index].append(cell)

    return tasks


# Принимает список задач(typing.List[Cell]), склеивает подряд идущие измененные студентом ячейки одного типа в одну.
def combine_modified_cells(tasks: typing.List[typing.List[Cell]]) -> typing.List[typing.List[Cell]]:
    combined_tasks = []

    for task in tasks:
        combined_task = []
        current_combined_text = []
        current_type = None

        for cell in task:
            if cell.is_changed:
                if current_type is None or cell.cell_type == current_type:
                    # первая такая ячейка или тип ячейки совпадает с текущей серией
                    current_combined_text.append(cell.cell_text)
                    current_type = cell.cell_type
                else:
                    # Если тип ячейки изменился.
                    if current_combined_text:
                        combined_task.append(
                            Cell(True, current_type, f"{SPECIAL_TOKEN}\n" + "\n".join(current_combined_text))
                        )
                        current_combined_text = [cell.cell_text]
                    current_type = cell.cell_type
            else:
                # Если встретим неизменённую ячейку, сохраним последовательность до нее
                if current_combined_text:
                    combined_task.append(
                        Cell(True, current_type, f"{SPECIAL_TOKEN}\n" + "\n".join(current_combined_text))
                    )
                    current_combined_text = []
                    current_type = None
                combined_task.append(cell)

        # Если остались не объединённые ячейки после цикла
        if current_combined_text:
            combined_task.append(Cell(True, current_type, f"{SPECIAL_TOKEN}\n" + "\n".join(current_combined_text)))

        combined_tasks.append(combined_task)

    return combined_tasks


EXPECTED_TASKS = 3
SPECIAL_TOKEN = "[ИЗМЕНЕНО СТУДЕНТОМ]."

if __name__ == "__main__":
    orig_work_path = "data/test.ipynb"
    orig_cells = get_filtered_notebook_cells_from_dir(orig_work_path)

    # for example only
    for notebook_path in ["test/done_work.ipynb"]:  # get_filenames_from_directory()
        student_cells = get_filtered_notebook_cells_from_dir(notebook_path)
        marked_cells = mark_modified_cells(orig_cells, student_cells)

        cleaned_tasks = parse_and_mark_cells_by_tasks(marked_cells, EXPECTED_TASKS)

        combined_tasks = combine_modified_cells(cleaned_tasks)

        for i, task in enumerate(combined_tasks):
            print(f"\n\n\nЗадание {i + 1}:\n")
            for cell_content in task:
                print(cell_content.cell_text)
                print("\n" * 5)
