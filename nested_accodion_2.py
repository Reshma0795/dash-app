import dash
from dash import html, dcc, Input, Output, State, ALL, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import sqlite3
from collections import defaultdict

# Initialize app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Referral Generator"
server = app.server

# Load data
file_path = 'nested_checklist.xlsx'
options_df = pd.read_excel(file_path, sheet_name="Options")
definitions_df = pd.read_excel(file_path, sheet_name="Definitions")
definitions = dict(zip(definitions_df["Service Function"], definitions_df["Definition"]))

# Database setup
conn = sqlite3.connect("referral_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS referral (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        option TEXT,
        service_function TEXT,
        header TEXT
    )
''')
conn.commit()

# Nest options
results = {}
for _, row in options_df.iterrows():
    service = row["Service Function"]
    header = row["Header"]
    option = row["Option"]
    results.setdefault(service, {}).setdefault(header, []).append(option)

# Accordion builder
def create_accordion():
    items = []
    for service, headers in results.items():
        definition = definitions.get(service, "No definition available.")
        sub_items = []
        for header, options in headers.items():
            checklist = dbc.Checklist(
                options=[{'label': html.Span(option), 'value': f"{service}|{header}|{option}"} for option in options],
                id={'type': 'service-checklist', 'index': f"{service}-{header}"}
            )
            sub_items.append(dbc.AccordionItem(checklist, title=header, item_id=f"{service}-{header}"))

        sub_accordion = dbc.Accordion(
            sub_items, flush=True, start_collapsed=True, always_open=True, id=f"sub-accordion-{service}"
        )

        items.append(
            dbc.AccordionItem(
                [html.P(definition), sub_accordion],
                title=service,
                item_id=service
            )
        )
    return items

# Layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='session-id-store'),
    html.Div(id='page-content')
])

# Page layout rendering
@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/referral":
        return referral_page()
    return main_page()

# Page: Main
def main_page():
    return dbc.Container([
        html.H2("List of Suggested Actions", className="my-4"),
        dcc.Store(id="session-id", storage_type="session"),
        dbc.Accordion(create_accordion(), start_collapsed=True, always_open=True, id="main-accordion"),
        html.Br(),
        dbc.Button("Generate Referral", id="generate-referral-btn", color="primary"),
    ], fluid=True)

# Page: Referral Summary
def referral_page():
    cursor.execute("SELECT session_id FROM referral ORDER BY id DESC LIMIT 1")
    last_session = cursor.fetchone()
    if not last_session:
        return dbc.Container([
            html.H2("Saved Referral"),
            html.P("No saved referrals found."),
            dbc.Button("Back", href="/", color="secondary", className="mt-3")
        ], fluid=True)

    session_id = last_session[0]
    cursor.execute('SELECT option, service_function, header FROM referral WHERE session_id = ?', (session_id,))
    rows = cursor.fetchall()

    # Group the data
    grouped_data = defaultdict(list)
    for option, service_function, header in rows:
        grouped_data[(option, header)].append(service_function)

    table_rows = []
    copy_lines = []  # this holds plain text for clipboard

    for (option, header), service_functions in grouped_data.items():
        if table_rows:
            table_rows.append(html.Tr([html.Td(colSpan=3, style={"height": "10px", "border": "none"})]))
            copy_lines.append("")  # blank line between groups

        for i, sf in enumerate(service_functions):
            table_rows.append(html.Tr([
                html.Td(option if i == 0 else "", style={"verticalAlign": "top"}),
                html.Td(sf),
                html.Td(header if i == 0 else "", style={"verticalAlign": "top"})
            ]))
            # Add to text for copy
            copy_lines.append(
                f"Option: {option if i == 0 else ''}\tService Function: {sf}\tHeader: {header if i == 0 else ''}"
            )

    return dbc.Container([
        html.H2("Your Referral Summary"),
        dbc.Table([
            html.Thead(html.Tr([
                html.Th("Option", style={"width": "30%"}),
                html.Th("Service Function", style={"width": "40%"}),
                html.Th("Header", style={"width": "30%"})
            ])),
            html.Tbody(table_rows)
        ], bordered=True, hover=False, responsive=True, className="table-fixed"),
        html.Br(),
        html.Div([
            html.Div("📋 Copy referral details:", style={"marginBottom": "8px"}),
            dcc.Clipboard(
                target_id="referral-plain-text",
                title="Copy",
                style={"fontSize": "14px", "padding": "6px 12px", "cursor": "pointer", "background": "#f1f1f1", "border": "1px solid #ccc"}
            ),
            html.Pre("\n".join(copy_lines), id="referral-plain-text", style={"display": "none"})
        ]),
        html.Br(),
        dbc.Button("Back", href="/", color="secondary")
    ], fluid=True)

# Callback to handle generate + redirect
@app.callback(
    Output("url", "pathname"),
    Input("generate-referral-btn", "n_clicks"),
    State({'type': 'service-checklist', 'index': ALL}, 'value'),
    State({'type': 'service-checklist', 'index': ALL}, 'id'),
    prevent_initial_call=True
)
def generate_referral_and_redirect(n_clicks, values, ids):
    import uuid
    session_id = str(uuid.uuid4())  # unique per click

    selected = []
    for value_list, id_dict in zip(values, ids):
        if value_list:
            for value in value_list:
                service, header, option = value.split("|")
                selected.append((session_id, option, service, header))

    if selected:
        cursor.executemany('INSERT INTO referral (session_id, option, service_function, header) VALUES (?, ?, ?, ?)', selected)
        conn.commit()

    return "/referral"

if __name__ == "__main__":
    app.run_server(debug=True)
