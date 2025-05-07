import dash
from dash import html, dcc, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import sqlite3
from collections import defaultdict
import os
import uuid
from dash import ctx
from dash.exceptions import PreventUpdate

# Initialize app
app = dash.Dash(__name__, external_stylesheets=["https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Referral Generator"
server = app.server

# Load data
file_path = 'SST_referral_options.xlsx'
options_df = pd.read_excel(file_path, sheet_name="Options")
definitions_df = pd.read_excel(file_path, sheet_name="Definitions")
definitions = dict(zip(definitions_df["Service Function"], definitions_df["Definition"]))

# Database setup
conn = sqlite3.connect("referral_database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS referral_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        service_function TEXT,
        sst_original_means TEXT,
        cgh_specific_means TEXT
    )
''')
conn.commit()

# Nest options
results = {}
for _, row in options_df.iterrows():
    service = row["Service Function"]
    header = row["SST_Original_Means"]
    option = row["CGH_Specific_Means"]
    results.setdefault(service, {}).setdefault(header, []).append(option)

# Accordion builder
def create_accordion():
    items = []
    for service, headers in results.items():
        definition = definitions.get(service, "No definition available.")
        info_icon_id = f"info-icon-{service.replace(' ', '-').replace('/', '').replace(',', '').lower()}"
        sub_items = []
        for header, options in headers.items():
            checklist = dbc.Checklist(
                options=[{'label': html.Span(option), 'value': f"{service}|{header}|{option}"} for option in options],
                id={'type': 'service-checklist', 'index': f"{service}|||{header}"})
            sub_items.append(dbc.AccordionItem(checklist, title=header, item_id=f"{service}-{header}"))

        sub_accordion = dbc.Accordion(
            sub_items, flush=True, start_collapsed=True, always_open=True, id=f"sub-accordion-{service}", className="sub-accordion")
        accordion_header = html.Span([
            html.Span(service),
            html.I(className="fa fa-info-circle", id=info_icon_id, style={
                "cursor": "pointer",
                "marginLeft": "8px",
                "color": "#0d6efd",
                "fontSize": "14px"}),
            dbc.Popover(
                [dbc.PopoverHeader("Definition"),dbc.PopoverBody(definition)],
                id=f"popover-{info_icon_id}",
                target=info_icon_id,
                trigger="hover",
                placement="right",
                style={"maxWidth": "300px"})
        ])

        items.append(
            html.Div([
                dbc.AccordionItem(
                    sub_accordion,
                    title=accordion_header,
                    item_id=service
                )
            ], style={
                "border": "3px solid #F06D1A",     # Darker border for main level
                "borderRadius": "8px",
                "marginBottom": "4px",
                "boxShadow": "0 2px 4px rgba(0, 0, 0, 0.08)",
                "backgroundColor": "#FFFFFFB2"       # Subtle gray background
            })
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
        html.H2("List of Suggested Actions", className="my-4 text-center"),
        dcc.Store(id="session-id", storage_type="session"),
        dbc.Accordion(create_accordion(), start_collapsed=True, always_open=True, id="main-accordion", className="main-accordion"),
        html.Br(),
        dbc.Row(
        dbc.Col(dbc.Button("Generate Referral", id="generate-referral-btn", color="primary"),width="auto"),justify="center",className="my-4")
    ], fluid=True)

# Page: Referral Summary
def referral_page():
    cursor.execute("SELECT session_id FROM referral_records ORDER BY id DESC LIMIT 1")
    last_session = cursor.fetchone()
    if not last_session:
        return dbc.Container([
            html.H2("Saved Referral"),
            html.P("No saved referrals found."),
            dbc.Button("Back", href="/", color="secondary", className="mt-3")], fluid=True)

    session_id = last_session[0]
    cursor.execute('SELECT service_function, sst_original_means,cgh_specific_means FROM referral_records WHERE session_id = ?', (session_id,))
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
                #html.Td(header if i == 0 else "", style={"verticalAlign": "top"})
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
            #copy_lines.append(f"  Means from Original SST: {header}")
            copy_lines.append("")

    return dbc.Container([
        html.H2("Your Referral Summary", className="my-4 text-center"),
        dbc.Table([
            html.Thead(html.Tr([
                html.Th("CGH Specific Means", style={"width": "30%"}),
                html.Th("Service Function / Need", style={"width": "40%"}),
                #html.Th("Means from Original SST", style={"width": "30%"})
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
    session_id = str(uuid.uuid4())  # unique per click

    selected = []
    for value_list, id_dict in zip(values, ids):
        if value_list:
            for value in value_list:
                service, header, option = value.split("|")
                selected.append((session_id, option, service, header))

    if selected:
        cursor.executemany('INSERT INTO referral_records (session_id, service_function, sst_original_means,cgh_specific_means) VALUES (?, ?, ?, ?)', selected)
        conn.commit()

    return "/referral"

# Callback to sync repeated "means" options across checklists
@app.callback(
    Output({'type': 'service-checklist', 'index': ALL}, 'value'),  # update all checklist values
    Input({'type': 'service-checklist', 'index': ALL}, 'value'),   # whenever any checklist changes
    State({'type': 'service-checklist', 'index': ALL}, 'id'),      # get checklist ids
    prevent_initial_call=True
)
def sync_selected_options(values_all, ids_all):
    if not ctx.triggered_id:
        raise PreventUpdate

    # Step 1: Identify which checklist was interacted with
    changed_index = ctx.triggered_id['index']

    # Step 2: Gather all options selected anywhere across the UI
    selected_options_global = set()
    for group in values_all or []:
        for val in group or []:
            try:
                _, header, opt = val.split("|")
                selected_options_global.add((header, opt))
            except:
                continue

    # Step 3: Determine which checklist was changed, and preserve its own selections
    changed_index_position = None
    changed_local_options = set()
    for i, id_dict in enumerate(ids_all):
        if id_dict["index"] == changed_index:
            changed_index_position = i
            for val in values_all[i]:
                try:
                    _, _, opt = val.split("|")
                    changed_local_options.add(opt)
                except:
                    continue
            break

    if changed_index_position is None:
        raise PreventUpdate

    # Step 4: Update all checklist values
    updated_values = []
    for i, id_dict in enumerate(ids_all):
        service, header = id_dict["index"].split("|||")
        options_here = results[service][header]

        if i == changed_index_position:
            # Don't modify the checklist the user touched
            new_values = values_all[i]
        else:
            # Add any options that are selected anywhere
            new_values = []
            for opt in options_here:
                if (header, opt) in selected_options_global:
                    full_val = f"{service}|{header}|{opt}"
                    new_values.append(full_val)

        updated_values.append(new_values)

    return updated_values

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>

        .main-accordion .accordion-button:focus {
            box-shadow: none !important;
        }

        .main-accordion .accordion-button:not(.collapsed) {
            background-color: #a8aaad !important;
            color: #333 !important;
        }

        .sub-accordion .accordion-button:focus {
            box-shadow: none !important;
        }

        .sub-accordion .accordion-button:not(.collapsed) {
            background-color: #7b9ac9 !important;
            color: #000 !important;
        }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=True, host="0.0.0.0", port=port)
    #app.run_server(debug=True)
