from bs4 import BeautifulSoup

def insert_string_before_tag(html_filename, string_to_insert, tag):
    with open(html_filename, 'r') as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the tag before which you want to insert the string
    target_tag = soup.find(tag)
    if target_tag:
        # Create a new string to insert
        new_tag = soup.new_tag('tr')
        new_tag.append(soup.new_tag('td', string="New Row"))

        # Insert the new string before the target tag
        target_tag.insert_before(new_tag)

        # Write the modified HTML back to the file
        with open(html_filename, 'w') as file:
            file.write(str(soup))
        print("String inserted successfully.")
    else:
        print("Tag not found in the HTML file.")

# Usage example
html_filename = "example.html"  # Update this with your HTML file name
string_to_insert = "New Row"
tag_to_find = "table"
insert_string_before_tag(html_filename, string_to_insert, tag_to_find)
