import dash
from dash import html, dcc, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import sqlite3
from collections import defaultdict
import os

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
        dbc.Row(
        dbc.Col(dbc.Button("Generate Referral", id="generate-referral-btn", color="primary"),width="auto"),justify="center",className="my-4")
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

    # Group data by option and header
    grouped_data = defaultdict(list)
    for option, service_function, header in rows:
        grouped_data[(option, header)].append(service_function)

    # ----- Table Rows -----
    table_rows = []
    for (option, header), service_functions in grouped_data.items():
        if table_rows:
        # Add a light separator row between groups
            table_rows.append(
                html.Tr([
                    html.Td(colSpan=3, style={
                        "height": "8px",
                        "borderTop": "2px solid #ddd",
                        "backgroundColor": "#f9f9f9"
                    })
                ])
            )

        for i, service_function in enumerate(service_functions):
            table_rows.append(html.Tr([
                html.Td(option if i == 0 else "", style={"verticalAlign": "top"}),
                html.Td(service_function),
                html.Td(header if i == 0 else "", style={"verticalAlign": "top"})
            ]))

    # ----- Copy Lines -----
    # Group by option and header with joined service functions
    condensed = defaultdict(lambda: defaultdict(list))
    for option, service_function, header in rows:
        condensed[option][header].append(service_function)

    copy_lines = []
    for option, headers in condensed.items():
        for header, functions in headers.items():
            copy_lines.append(f"CGH Specific Means: {option}")
            copy_lines.append(f"- Service Function/Needs: {', '.join(functions)}")
            copy_lines.append(f"  Means from Original SST: {header}")
            copy_lines.append("")

    return dbc.Container([
        html.H2("Your Referral Summary"),
        dbc.Table([
            html.Thead(html.Tr([
                html.Th("CGH Specific Means", style={"width": "30%"}),
                html.Th("Service Function / Need", style={"width": "40%"}),
                html.Th("Means from Original SST", style={"width": "30%"})
            ])),
            html.Tbody(table_rows)
        ], bordered=True, hover=False, responsive=True, className="table-fixed"),
        html.Br(),
        html.Div([
            html.Div([
    html.Div([
        html.Span("Copy referral details:", style={"fontWeight": "600", "marginRight": "10px"}),
        dcc.Clipboard(
            target_id="referral-plain-text",
            title="Copy",
            style={
                "fontSize": "16px",
                "cursor": "pointer",
                "verticalAlign": "middle"
            }
        )
    ], style={
        "display": "flex",
        "alignItems": "center",
        "padding": "10px",
        "border": "1px solid #ccc",
        "borderRadius": "6px",
        "backgroundColor": "#f8f9fa",
        "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.05)",
        "width": "fit-content"
    })
], className="my-3"),


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

