from pathlib import Path

import plotly.graph_objects as go

# Create a comprehensive flowchart using Plotly
fig = go.Figure()

# Define positions for flowchart elements
positions = {
    'start': (0, 9),
    'decision': (0, 7.5),
    'bs_approach': (-2.5, 6),
    'playwright_approach': (2.5, 6),
    'fast_scraping': (-2.5, 4.5),
    'js_handling': (2.5, 4.5),
    'extract_data': (0, 3),
    'parse_data': (0, 1.5),
    'filter_data': (0, 0),
    'export': (0, -1.5)
}

# Colors from the brand palette
colors = ['#1FB8CD', '#DB4545', '#2E8B57', '#5D878F', '#D2BA4C']

# Add rectangles for process steps
rectangles = [
    ('start', 'Run run_diagnostics.py', colors[0]),
    ('bs_approach', 'Use BeautifulSoup<br>approach', colors[2]),
    ('playwright_approach', 'Use Playwright<br>approach', colors[3]),
    ('fast_scraping', 'Fast scraping<br>no browser needed', colors[4]),
    ('js_handling', 'Handles JavaScript<br>rendering', colors[1]),
    ('extract_data', 'Extract data from tables', colors[0]),
    ('parse_data', 'Parse schedule, stats,<br>standings', colors[2]),
    ('filter_data', 'Filter by date range<br>last week, current week', colors[3]),
    ('export', 'Export to JSON/CSV', colors[4])
]

for key, text, color in rectangles:
    x, y = positions[key]
    fig.add_shape(
        type="rect",
        x0=x-1, y0=y-0.4, x1=x+1, y1=y+0.4,
        fillcolor=color,
        opacity=0.7,
        line=dict(color="black", width=2)
    )
    
    fig.add_annotation(
        x=x, y=y,
        text=text,
        showarrow=False,
        font=dict(size=11, color="black"),
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="black",
        borderwidth=1
    )

# Add diamond for decision
x, y = positions['decision']
fig.add_shape(
    type="path",
    path=f"M {x-1.2},{y} L {x},{y+0.6} L {x+1.2},{y} L {x},{y-0.6} Z",
    fillcolor=colors[1],
    opacity=0.7,
    line=dict(color="black", width=2)
)

fig.add_annotation(
    x=x, y=y,
    text="Is data in<br>HTML source?",
    showarrow=False,
    font=dict(size=10, color="black"),
    bgcolor="rgba(255,255,255,0.8)"
)

# Add arrows and connections
arrows = [
    # Start to decision
    (positions['start'], positions['decision']),
    # Decision to approaches
    (positions['decision'], positions['bs_approach']),
    (positions['decision'], positions['playwright_approach']),
    # Approaches to outcomes
    (positions['bs_approach'], positions['fast_scraping']),
    (positions['playwright_approach'], positions['js_handling']),
    # Outcomes to extract
    (positions['fast_scraping'], positions['extract_data']),
    (positions['js_handling'], positions['extract_data']),
    # Linear flow
    (positions['extract_data'], positions['parse_data']),
    (positions['parse_data'], positions['filter_data']),
    (positions['filter_data'], positions['export'])
]

for (x1, y1), (x2, y2) in arrows:
    # Adjust arrow positions to not overlap with shapes
    if y1 > y2:  # Downward arrow
        y1 -= 0.4
        y2 += 0.4
    elif y1 < y2:  # Upward arrow
        y1 += 0.4
        y2 -= 0.4
    
    if x1 != x2:  # Diagonal arrows
        if x1 < x2:  # Right diagonal
            x1 += 1
            x2 -= 1
        else:  # Left diagonal
            x1 -= 1
            x2 += 1
    
    fig.add_annotation(
        x=x2, y=y2,
        ax=x1, ay=y1,
        xref='x', yref='y',
        axref='x', ayref='y',
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=2,
        arrowcolor="black",
        showarrow=True
    )

# Add YES/NO labels for decision branches
fig.add_annotation(x=-1.2, y=6.8, text="YES", showarrow=False, font=dict(size=12, color="green"))
fig.add_annotation(x=1.2, y=6.8, text="NO", showarrow=False, font=dict(size=12, color="red"))

# Configure layout
fig.update_layout(
    title="Amherst Hockey Scraping Decision Process",
    xaxis=dict(range=[-4, 4], showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(range=[-3, 10], showgrid=False, zeroline=False, showticklabels=False),
    plot_bgcolor='white',
    showlegend=False,
    font=dict(family="Arial", size=12)
)

# Save the flowchart
output_dir = Path("docs")
output_dir.mkdir(parents=True, exist_ok=True)
fig.write_image(str(output_dir / "flowchart.png"))
fig.write_image(str(output_dir / "flowchart.svg"), format='svg')

print("Professional flowchart created successfully!")
