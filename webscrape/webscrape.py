import requests
import bs4
from bs4 import BeautifulSoup
import re
import csv

test = False

"""
Extracts the Pokémon name from a string, stopping at "Basic" or "Stage 1".
Args:
    text: The string containing the Pokémon information.
Returns:
    The extracted Pokémon name (up to "Basic" or "Stage 1").
"""
def extract_pkmn_evo_stage(text):
  stop_index = None
  if text.find('Pokémon'):
    stop_index = text.find('Pokémon')
  # Extract the Pokémon name (up to the stop word)
  if stop_index is not None:
    pokemon_name = text[:stop_index].strip()
  else:
    pokemon_name = text  # No stop word found, return entire text
  return pokemon_name

def extract_pkmn_prev_evo_stage(text):
  stop_index = None
  if text.find('Pokémon'):
    stop_index = text.find('Pokémon')
  # Extract the Pokémon name (up to the stop word)
  if stop_index is not None:
    pokemon_name = text[:stop_index].strip()
  else:
    pokemon_name = text  # No stop word found, return entire text
  return pokemon_name  

#---------------------------------BEGIN extract_english_text FUNCTION---------------------------------#
def extract_english_text(text, keep_punc):
  """
  Extracts English text from a given string.

  Args:
      text: The string to extract English text from.

  Returns:
      A string containing only the English text from the input.
  """
  # Replace Japanese characters with an empty string
  japanese_pattern = re.compile("[ぁ-んァ-ンﾞﾟー]")
  english_text = japanese_pattern.sub('', text)

  # Remove punctuation and special characters
  if keep_punc != True:
    punc_pattern = re.compile("[^\w\s]")
    english_text = punc_pattern.sub('', english_text)

  # Return the filtered English text
  return english_text
  #---------------------------------END extract_english_text FUNCTION---------------------------------#

#---------------------------------BEGIN scrape_pokemon_info FUNCTION---------------------------------#
def scrape_pokemon_info(url):
  """Scrapes Pokemon information from a Bulbapedia page."""
  response = requests.get(url)
  html_soup = BeautifulSoup(response.content, 'html.parser')

  # Extract basic information
  pkmn_name_with_set = html_soup.select('h1#firstHeading span.mw-page-title-main')[0].get_text()

  pkmn_info_table_rows = html_soup.select('div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr') 
  pkmn_evo_stage = extract_pkmn_evo_stage(pkmn_info_table_rows[0].find('td').text.strip())
  pkmn_prev_evo = None

  if pkmn_info_table_rows[0].find('td').find('small') != None:
    dirty_prev_evo_stage = pkmn_info_table_rows[0].find('td').find('small').get_text()
    start_index = dirty_prev_evo_stage.find('Evolves from ')
    end_index = start_index + len('Evolves from ')
    pkmn_prev_evo = dirty_prev_evo_stage[end_index:].strip()
  
  pkmn_name = pkmn_info_table_rows[1].find('td').text.strip().replace("\xa0", "-")
  pkmn_type = pkmn_info_table_rows[2].find('td').text.strip()
  pkmn_hp = pkmn_info_table_rows[3].find('td').text.strip()

  # Extract weakness, resistance, retreat cost
  # Laughably bad website design so there is a one row table in the overall table w/ pokemon info
  # Also very painful to extract weakness resistance and retreat cost due to no direct text, so need to put guardrails in case any of these don't exist
  # For retreat cost, each "1" retreat cost is represented by an image of a colorless energy, which is why the img count is used
  weak_res_ret_table_rows = html_soup.select('div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr:nth-child(5) td table tbody tr th') 
  pkmn_weakness = weak_res_ret_table_rows[0].find('a').attrs['title'] if weak_res_ret_table_rows[0].find('a') else None
  pkmn_resistance = weak_res_ret_table_rows[1].find('a').attrs['title'] if weak_res_ret_table_rows[1].find('a') else None
  pkmn_retreat_cost = len(weak_res_ret_table_rows[2].find_all('img'))

  # Extract English card details
  pkmn_set_info_table_rows = html_soup.select('div#mw-content-text table tr:nth-child(3) > td > table:nth-child(2) > tbody > tr td:nth-child(2)') 
  pkmn_english_expansion = pkmn_set_info_table_rows[0].text.strip()

  # Extract move information
  # First row is the move, second row is the move effect
  # Iteration 0: targets rows 0 and 1
  # Iteration 1: targets rows 2 and 3
  # Iteration x: targets rows 2*x and 2*x+1
  moves_info_table_rows = html_soup.select('#Card_text')[0].parent.find_next_sibling().find('tbody').find_all('tr', recursive=False)
  # moves_info_table_rows = list(html_soup.select('div.mw-parser-output table.roundy')[0].find('tbody').children)

  pkmn_moves = []
  pkmn_ability = None
  skip_row_one = False
  skip_row_two = False
  # for idx in range(0, len(moves_info_table_rows)):
  #   print(idx)
  #   print(moves_info_table_rows[idx])
  #   print('\n')
  """
  Breakdown of move parsing rules
  Each move has 2 rows, one for non description and one for description. If there is no description, the row is hidden.
  1. No ability or past/future
     - start from 0 and go 2 by 2
     - move nondescrip is on x
     - move descrip is on x+1
  """
  if moves_info_table_rows:
    idx = 0
    while idx < len(moves_info_table_rows):
      # print(idx)
      if moves_info_table_rows[idx].find('img', alt='Future paradox') != None: # for some reason this also seems to work on Ancient
        idx = idx + 1
        skip_row_one = True
      '''
      Find all moves on the current page
      Note that in move_info_table_rows, the first row is all non effect info and the second row is effect info
      If there is no effect, then the second row is hidden 
      '''
      cur_pkmn_move = {}
      move_info_wo_desc = moves_info_table_rows[idx].find('td').find('table').find('tbody').find('tr')
      if move_info_wo_desc.find(href=re.compile("Ability")):
        pkmn_ability_name = extract_english_text(move_info_wo_desc.find('td', style='text-align: center; color:#7E0A0E;').get_text(), False).replace('\n', '')
        pkmn_ability_desc = extract_english_text(moves_info_table_rows[idx + 1].get_text(), True).replace('\n', '')
        pkmn_ability = { 'Ability Name': pkmn_ability_name, 'Ability Desc': pkmn_ability_desc }
        idx = idx + 2
        skip_row_two = True
        continue

      dirty_move_cost = []
      potential_nonuseless_info = move_info_wo_desc.find('th', class_='roundyleft') # useless info is the ex rule

      if potential_nonuseless_info is not None:  # Check for existence of the target tag
        has_anchor_descendants = any(descendant.name == 'a' for descendant in potential_nonuseless_info.descendants)
        if has_anchor_descendants:
          move_cost_links = potential_nonuseless_info.find_all('a')
          dirty_move_cost.extend(move_cost_links)  # Add valid links to the list
      '''
      For each energy found in dirty_move_cost, retrieve the energy type
      - If the energy type is not found, set the counter for corresponding energy type to 1
      - If the energy type is found, increment the counter for corresponding energy type by 1
      '''
      move_cost = {}
      for idx2 in range(len(dirty_move_cost)):
        if dirty_move_cost[idx2] == None:
          continue
        energy_type = dirty_move_cost[idx2].attrs['title']
        energy_cur_count = 0
        if energy_type in move_cost:
            energy_cur_count = move_cost[energy_type]

        move_cost[energy_type] = energy_cur_count + 1
      # print(move_cost)
      cur_pkmn_move['Move Cost'] = move_cost
      dirty_move_name = []
      dirty_move_name_test = move_info_wo_desc.find('th', class_='roundyleft') 

      # print(move_info_wo_desc)
      if dirty_move_name_test is not None:  # Check for existence of the target tag
        dirty_move_name = move_info_wo_desc.find('th', class_='roundyleft').find_next_sibling().get_text()
      else:
        idx = idx + 1
        continue
      cur_pkmn_move['Move Name'] = extract_english_text(dirty_move_name, False).replace(' \n', '')

      if move_info_wo_desc.find('th', class_='roundyright').get_text() != '\n':
        dirty_move_damage = move_info_wo_desc.find('th', class_='roundyright').get_text().replace(' \n', '')
        multiplier_index = dirty_move_damage.find('×')
        add_index = dirty_move_damage.find('+')

        if multiplier_index >= 0:
          cur_pkmn_move['Move Damage'] = dirty_move_damage[:multiplier_index]
          cur_pkmn_move['Move Damage Modifier'] = ('multiply', dirty_move_damage[:multiplier_index])
          cur_pkmn_move['Move Damage Maximum Procs'] = 'TOFILL'
          cur_pkmn_move['Move Damage Modifier Template'] = 'TOFILL'
        elif add_index >= 0:
          cur_pkmn_move['Move Damage'] = dirty_move_damage[:add_index]
          cur_pkmn_move['Move Damage Modifier'] = ('add', dirty_move_damage[:add_index])
          cur_pkmn_move['Move Damage Maximum Procs'] = 'TOFILL'
          cur_pkmn_move['Move Damage Modifier Template'] = 'TOFILL'
        else:
          cur_pkmn_move['Move Damage'] = dirty_move_damage.replace('\n', '')
          cur_pkmn_move['Move Damage Modifier'] = None
      else:
        cur_pkmn_move['Move Damage'] = None
        cur_pkmn_move['Move Damage Modifier'] = None
      # print(idx)
      # print(moves_info_table_rows[idx+5])
      # print(type(moves_info_table_rows[idx+5]))
      if idx + 1 < len(moves_info_table_rows) and isinstance(moves_info_table_rows[idx + 1], bs4.element.Tag):
        # print(moves_info_table_rows[idx+5])
        cur_pkmn_move['Move Effect'] = moves_info_table_rows[idx + 1].get_text().replace('\n', '')
      else:
        cur_pkmn_move['Move Effect'] = None
      # print(cur_pkmn_move)
      pkmn_moves.append(cur_pkmn_move)
      idx = idx + 2

  # Return extracted information
  return {
      "Name": pkmn_name,
      "Name w/ Set": pkmn_name_with_set,
      "Evolution Stage": pkmn_evo_stage,
      "Previous Evolution": pkmn_prev_evo,
      "Ability": pkmn_ability,
      "HP": pkmn_hp,
      'Type': pkmn_type,
      "Weakness": pkmn_weakness,
      "Resistance": pkmn_resistance,
      "Retreat Cost": pkmn_retreat_cost,
      "Moves": pkmn_moves,
  }
#---------------------------------END scrape_pokemon_info FUNCTION---------------------------------#

# TODO: 
# comment
# correct bug with not retrieving moves for paradox monss
# fill in missing/incorrect information
# convert to database and make sample query

expansion_url = "https://bulbapedia.bulbagarden.net/wiki/Temporal_Forces_(TCG)"
response = requests.get(expansion_url)
html_soup = BeautifulSoup(response.content, 'html.parser')
card_list_rows = html_soup.select('#Card_lists')[0].parent.find_next_sibling().find('table', class_='roundy').find('tbody').find_all('tr', recursive=False)[1].find('td').find('table').find('tbody').find_all('tr', recursive=False)

# skip the first row
all_pkmn_cards = []
if test != True: 
  for i in range(1, len(card_list_rows) - 1):
  # for i in range(1, 5):
    # print(card_list_rows[i].find('th').get_text())
    if card_list_rows[i].find('th', style='background:#FFFFFF;'):
      pkmn_card_type = card_list_rows[i].find('th').find('img').attrs['alt']
    else:
      break

    card_list_row_info = card_list_rows[i].find_all('td', recursive=False)
    pkmn_card_no = card_list_row_info[0].get_text().replace('\n', '')
    pkmn_card_mark = card_list_row_info[1].find('a').attrs['title']
    pkmn_card_link = card_list_row_info[2].find('a').attrs['href']
    pkmn_card_rarity = card_list_row_info[3].find('a').attrs['title']

    pkmn_data = scrape_pokemon_info('https://bulbapedia.bulbagarden.net' + str(pkmn_card_link))
    pkmn_data['Card No'] = pkmn_card_no
    pkmn_data['Card Mark'] = pkmn_card_mark
    pkmn_data['Card Rarity'] = pkmn_card_rarity

    print(pkmn_data)
    all_pkmn_cards.append(pkmn_data)
else:
  pkmn_data = scrape_pokemon_info('https://bulbapedia.bulbagarden.net/wiki/Iron_Leaves_ex_(Temporal_Forces_25)')
  print(pkmn_data)
  all_pkmn_cards.append(pkmn_data)

  pkmn_data = scrape_pokemon_info('https://bulbapedia.bulbagarden.net/wiki/Iron_Valiant_(Temporal_Forces_80)')
  print(pkmn_data)
  all_pkmn_cards.append(pkmn_data)

# Get all keys from the first dictionary (assuming all dictionaries have the same keys)
keys = list(all_pkmn_cards[0].keys())

# Open a CSV file for writing
with open('pokemon_data.csv', 'w', newline='') as csvfile:
  # Create a CSV writer object
  writer = csv.DictWriter(csvfile, fieldnames=keys)
  # Write the header row
  writer.writeheader()
  # Write each dictionary as a row in the CSV
  for item in all_pkmn_cards:
    writer.writerow(item)

print("CSV file created successfully: pokemon_data.csv")

# print(all_pkmn_cards)

# print(len(card_list))
# url = "https://bulbapedia.bulbagarden.net/wiki/Scyther_(Temporal_Forces_1)"
# url = "https://bulbapedia.bulbagarden.net/wiki/Torterra_ex_(Temporal_Forces_12)"