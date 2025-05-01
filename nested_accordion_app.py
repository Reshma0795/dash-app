import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Simulated data (like after reading from Excel and processing)
results = {
    "Support of daily living function": {
        "Assisted living": ["Sheltered home", "Destitute home", "Adult disable home"],
        "Family or friend (close by)": ["Family or friend (close by)"],
        "Family or friend (not close by)": ["Family or friend (not close by)"],
        "Foreign Domestic Worker": ["Foreign Domestic Worker"],
        "High level center based care": ["Day care", "Dementia day care", "Day hospice care", "Day rehabilitation", "Centre-based nursing", "Night respite", "Geriatric day hospital"],


    },
    "Palliative Care Services": {
        "Header 1": ["Option E", "Option F"]
    }
}

# Simulated definitions (could also come from Excel)
definitions = {
    "Regular Primary Care Services": "Definition for Regular Primary Care.",
    "Palliative Care Services": "Definition for Palliative Care Services."
}

# Create nested accordions for each service function
service_functions_ui = []

for service, headers in results.items():
    definition_text = definitions.get(service, "No definition available.")
    sub_accordion_items = []

    for header, options in headers.items():
        checklist = dbc.Checklist(
            options=[{'label': html.Span(option), 'value': option} for option in options],
            id={'type': 'service-checklist', 'index': f"{service}-{header}"}
        )
        sub_accordion_items.append(
            dbc.AccordionItem(
                checklist,
                title=header,
                item_id=f"{service}-{header}"
            )
        )

    service_functions_ui.append(
        dbc.AccordionItem(
            [
                html.P(definition_text),
                dbc.Accordion(
                    sub_accordion_items,
                    flush=True,
                    start_collapsed=True,
                    always_open=False,
                    id=f"sub-accordion-{service}"
                )
            ],
            title=service,
            item_id=service
        )
    )

# Full layout
app.layout = dbc.Container([
    html.H2("Nested Accordion Example", className="my-4"),
    dbc.Accordion(
        service_functions_ui,
        start_collapsed=True,
        always_open=False,
        id="main-accordion"
    )
], fluid=True)

if __name__ == "__main__":
    app.run_server(debug=True)
