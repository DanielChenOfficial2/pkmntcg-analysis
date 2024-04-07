import requests
from bs4 import BeautifulSoup
import bs4

def scrape_pokemon_info(url):
  """Scrapes Pokemon information from a Bulbapedia page."""
  response = requests.get(url)
  html_soup = BeautifulSoup(response.content, 'html.parser')

  # Extract basic information
  pkmn_name_with_set = html_soup.select('h1#firstHeading')[0].text.strip()

  pkmn_info_table_rows = html_soup.select('div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr td') 
  pkmn_evo_stage = pkmn_info_table_rows[0].text.strip()
  pkmn_name = pkmn_info_table_rows[1].text.strip()
  pkmn_type = pkmn_info_table_rows[2].text.strip()
  pkmn_hp = pkmn_info_table_rows[3].text.strip()

  # Extract weakness, resistance, retreat cost
  # Laughably bad website design so there is a one row table in the overall table w/ pokemon info
  # Also very painful to extract weakness resistance and retreat cost due to no direct text, so need to put guardrails in case any of these don't exist
  # For retreat cost, each "1" retreat cost is represented by an image of a colorless energy, which is why the img count is used
  weak_res_ret_table_rows = html_soup.select('div#mw-content-text table tr:nth-child(3) > td > table > tbody > tr:nth-child(5) td table tbody tr th') 
  pkmn_weakness = weak_res_ret_table_rows[0].find('a').attrs['title'] if weak_res_ret_table_rows[0].find('a') else 'None'
  pkmn_resistance = weak_res_ret_table_rows[1].find('a').attrs['title'] if weak_res_ret_table_rows[1].find('a') else 'None'
  pkmn_retreat_cost = len(weak_res_ret_table_rows[2].find_all('img'))

  # Extract English card details
  pkmn_set_info_table_rows = html_soup.select('div#mw-content-text table tr:nth-child(3) > td > table:nth-child(2) > tbody > tr td:nth-child(2)') 
  pkmn_english_expansion = pkmn_set_info_table_rows[0].text.strip()
  pkmn_rarity = pkmn_set_info_table_rows[1].find('a').attrs['title']
  pkmn_card_no = pkmn_set_info_table_rows[2].text.strip()

  # Extract move information
  # First row is the move, second row is the move effect
  # Iteration 0: targets rows 0 and 1
  # Iteration 1: targets rows 2 and 3
  # Iteration x: targets rows 2*x and 2*x+1
  moves_info_table_rows = list(html_soup.select('div.mw-parser-output table.roundy')[0].find('tbody').children)

  pkmn_moves = []
  if moves_info_table_rows:
    for idx in range(0, len(moves_info_table_rows), 4):
      '''
      Find all moves on the current page
      Note that in move_info_table_rows, the first row is all non effect info and the second row is effect info
      If there is no effect, then the second row is hidden 
      '''
      cur_pkmn_move = {}
      # print(idx)
      # print(moves_info_table_rows[6])
      move_info_wo_desc = moves_info_table_rows[idx].find('td').find('table').find('tbody').find('tr')
      # print(move_info_wo_desc)
      # print('\n')
      dirty_move_cost = move_info_wo_desc.find('th', class_='roundyleft').find_all('a')
      # print(len(dirty_move_cost))

      '''
      For each energy found in dirty_move_cost, retrieve the energy type
      - If the energy type is not found, set the counter for corresponding energy type to 1
      - If the energy type is found, increment the counter for corresponding energy type by 1
      '''
      move_cost = {}
      for idx in range(len(dirty_move_cost)):
        energy_type = dirty_move_cost[idx].attrs['title']
        energy_cur_count = 0
        if energy_type in move_cost:
            energy_cur_count = move_cost[energy_type]

        move_cost[energy_type] = energy_cur_count + 1
      # print(move_cost)
      cur_pkmn_move['Move Cost'] = move_cost

      dirty_move_name = move_info_wo_desc.find('th', class_='roundyleft').find_next_sibling().get_text()
      cur_pkmn_move['Move Name'] = dirty_move_name.split()[0]

      cur_pkmn_move['Move Damage'] = int(move_info_wo_desc.find('th', class_='roundyright').get_text())

      cur_pkmn_move['Move Effect'] = ''
      # print(idx)
      # print(moves_info_table_rows[idx+5])
      # print(type(moves_info_table_rows[idx+5]))
      if isinstance(moves_info_table_rows[idx+5], bs4.element.Tag):
        # print(moves_info_table_rows[idx+5])
        cur_pkmn_move['Move Effect'] = moves_info_table_rows[idx+5].get_text().replace('\n', '')

      # print(cur_pkmn_move)
      pkmn_moves.append(cur_pkmn_move)

  # Return extracted information
  return {
      "Name": pkmn_name,
      "Name w/ Set": pkmn_name_with_set,
      "Evolution Stage": pkmn_evo_stage,
      "Type": pkmn_type,
      "HP": pkmn_hp,
      "Weakness": pkmn_weakness,
      "Resistance": pkmn_resistance,
      "Retreat Cost": pkmn_retreat_cost,
      "English Expansion": pkmn_english_expansion,
      "Rarity": pkmn_rarity,
      "Card No": pkmn_card_no,
      "Moves": pkmn_moves,
  }

# Example usage
url = "https://bulbapedia.bulbagarden.net/wiki/Scyther_(Temporal_Forces_1)"
# url = "https://bulbapedia.bulbagarden.net/wiki/Torterra_ex_(Temporal_Forces_12)"
pokemon_data = scrape_pokemon_info(url)

# Print information
print(pokemon_data)