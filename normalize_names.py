"""
Normalize Employee and Commission names in sales data.
- Employee: consistent format (trim spaces, fix known variants like Bir_ra -> Bir-ra)
- Commission: replace shorthand (adam, AlexS, DuaaZ) with full Employee names
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


# Employee name variants to canonical form (applies to Employee column)
EMPLOYEE_NORMALIZATIONS = {
    "Bir_ra Thanvi": "Bir-ra Thanvi",
    "Bir-ra B": "Bir-ra Thanvi",  # likely same person, variant
    "Molly ": "Molly Tasheva",  # trailing space variant
    "Leonard Masie": "Leonard Maisie",  # typo
    "Nicorescu Codruta": "Codruta Nicorescu",  # PYT uses different order
}


def extract_commission_parts(comm_str):
    """Parse 'name1: amt1, name2: amt2' into list of (name, amount_str)."""
    if not comm_str or not str(comm_str).strip():
        return []
    parts = []
    for segment in str(comm_str).split(","):
        segment = segment.strip()
        if ":" in segment:
            name = segment.split(":")[0].strip()
            rest = segment.split(":", 1)[1].strip()
            parts.append((name, rest))
    return parts


def build_commission_mapping(csv_path):
    """Infer commission shorthand -> full employee name from co-occurrence."""
    comm_to_emp = defaultdict(Counter)
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            emp = row.get("Employee", "").strip()
            if not emp:
                continue
            emp_canonical = EMPLOYEE_NORMALIZATIONS.get(emp, emp)
            emp_canonical = " ".join(emp_canonical.split())  # collapse spaces
            for comm_name, _ in extract_commission_parts(row.get("Commissions", "")):
                comm_to_emp[comm_name][emp_canonical] += 1

    mapping = {}
    for comm_name, emp_counts in comm_to_emp.items():
        if emp_counts:
            best_emp = emp_counts.most_common(1)[0][0]
            mapping[comm_name] = best_emp
    return mapping


def normalize_employee(emp, normalizations=None):
    """Normalize employee name: trim, apply known variants."""
    if not emp or (isinstance(emp, float) and emp != emp):
        return emp
    s = str(emp).strip()
    s = " ".join(s.split())  # collapse multiple spaces
    if normalizations and s in normalizations:
        return normalizations[s]
    return s


def normalize_commissions(comm_str, commission_mapping, employee_normalizations=None):
    """Replace commission shorthand with full employee names."""
    if not comm_str or not str(comm_str).strip():
        return comm_str
    parts = extract_commission_parts(comm_str)
    if not parts:
        return comm_str
    norms = employee_normalizations or {}
    result = []
    for name, amount in parts:
        full_name = commission_mapping.get(name, name)
        full_name = norms.get(full_name, full_name)  # apply employee normalizations
        result.append(f"{full_name}: {amount}")
    return ", ".join(result)


def normalize_csv(input_path, output_path=None):
    """Normalize Employee and Commission columns in a CSV file."""
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path

    commission_mapping = build_commission_mapping(input_path)
    all_normalizations = {**EMPLOYEE_NORMALIZATIONS}

    rows = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            emp = row.get("Employee", "")
            comm = row.get("Commissions", "")
            row["Employee"] = normalize_employee(emp, all_normalizations)
            row["Commissions"] = normalize_commissions(
                comm, commission_mapping, all_normalizations
            )
            rows.append(row)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return commission_mapping


def main():
    base = Path(__file__).parent
    files = [
        ("PYT Sales Data_rows.csv", "PYT Sales Data_rows_normalized.csv"),
        ("Opatra Sales Data_rows.csv", "Opatra Sales Data_rows_normalized.csv"),
    ]
    for inp, out in files:
        path = base / inp
        if not path.exists():
            print(f"Skipping {inp} (not found)")
            continue
        print(f"Normalizing {inp} -> {out}")
        mapping = normalize_csv(path, base / out)
        print(f"  Commission mappings: {len(mapping)}")


if __name__ == "__main__":
    main()
