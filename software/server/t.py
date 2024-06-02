from bokeh.io import show
from bokeh.layouts import column
from bokeh.models import Button, Div, CustomJS

# Sample long text
long_text = """
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. 
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor 
in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, 
sunt in culpa qui officia deserunt mollit anim id est laborum.
""" * 20  # Repeat the text to ensure it's long enough to require scrolling

# Create a scrollable Div widget
scrollable_div = Div(text=long_text, style={'overflow': 'auto', 'height': '200px', 'border': '1px solid black', 'padding': '10px'})

# Create a button to scroll the Div into view
button = Button(label="Scroll to Text", button_type="success")

# CustomJS callback to scroll the Div into view
callback = CustomJS(args=dict(div_id=scrollable_div.id), code="""
    const div_el = document.getElementById(div_id);
    if (div_el) {
        div_el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
""")

# Attach the callback to the button
button.js_on_click(callback)

# Arrange the widgets in a column layout
layout = column(button, scrollable_div)

# Show the layout
show(layout)