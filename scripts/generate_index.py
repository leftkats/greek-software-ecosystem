import yaml

# import random
from jinja2 import Environment, FileSystemLoader

# --- Configuration ---
YAML_PATH = "data/companies.yaml"
OUTPUT_PATH = "index.html"
ITEMS_PER_PAGE = 50
env = Environment(loader=FileSystemLoader("templates"))


# --- Helper Functions ---
def get_policy_style(policy):
    if not policy:
        return "hidden"
    p = str(policy).lower()
    if "remote" in p:
        return "bg-green-100 text-green-800"
    if "hybrid" in p:
        return "bg-yellow-100 text-yellow-800"
    return "bg-gray-100 text-gray-800"


# --- Load and Prepare Data ---
try:
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        companies_data = yaml.load(f, Loader=yaml.FullLoader)

    if not companies_data:
        # In case the company doesn't have jobs in Greece or YAML is empty
        print("No companies found in source.")
        companies_data = []

    all_sectors = set()
    for c in companies_data:
        # Assign random policy if missing as requested
        if not c.get("work_policy"):
            c["work_policy"] = "N/A"
        else:
            c["work_policy"] = str(c["work_policy"]).strip()
        for s in c.get("sectors", []):
            all_sectors.add(s)

    sorted_sectors = sorted(list(all_sectors))

except FileNotFoundError:
    print(f"Error: {YAML_PATH} not found.")
    exit()

# --- HTML Template ---
template = env.get_template("index_template.html")

# --- Build Execution ---
final_html = template.render(
    companies=companies_data,
    sectors=sorted_sectors,
    items_per_page=ITEMS_PER_PAGE,
    get_style=get_policy_style,
)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(final_html)

print("Website updated with specified Nav, Header, and Search UI components.")
