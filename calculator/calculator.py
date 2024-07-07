import pandas as pd
import ast
import csv
import json
import math
import re
from bs4 import BeautifulSoup
import os
import sys

test = False

# Expansion CSV files
expansion_csv_filename_arr = [
  "bs.csv",
  "ar.csv",
  "pg.csv",
  "lo.csv",
  "st.csv",
  "cz.csv",
  "sv.csv",
  "pe.csv",
  "of.csv",
  "151.csv",
  "pr.csv",
  "pf.csv",
  "tf.csv",
  "tm.csv"
]

# Expansion two letters
expansion_two_letters_arr = [
  "bs",
  "ar",
  "pg",
  "lo",
  "st",
  "cz",
  "sv",
  "pe",
  "of",
  "151",
  "pr",
  "pf",
  "tf",
  "tm"
]

# Expansion full name
expansion_name_arr = [
  "Brilliant Stars",
  "Astral Radiance",
  "Pokemon Go",
  "Lost Origin",
  "Silver Tempest",
  "Crown Zenith",
  "Scarlet and Violet",
  "Paldea Evolved",
  "Obsidian Flames",
  "151",
  "Paradox Rift",
  "Paldean Fates",
  "Temporal Forces",
  "Twilight Masquerade"
]

# Expansion image prefix
expansion_img_prefix_arr = [
  "BRS",
  "ASR",
  "PGO",
  "LOR",
  "SIT",
  "CRZ",
  "SVI",
  "PAL",
  "OBF",
  "MEW",
  "PAR",
  "PAF",
  "TEF",
  "TWM"
]

# Verify conditions of poketool or supporter to see if it can be used in the current conditions of pkmn and enemy_pkmn
def can_use_card(pkmn_data, enemy_pkmn, card_condition):
  is_condition_fulfilled = True
  condition_string = ''
  for key, value in card_condition.items():
    if key == 'Pkmn Card Type':
      if value in ast.literal_eval(pkmn_data['Card Type']):
        continue
      is_condition_fulfilled = False
      break
    elif key == 'Enemy Pkmn Card Type':
      if not isinstance(enemy_pkmn, pd.Series):
        is_condition_fulfilled = False
        break
  
      if value in ast.literal_eval(enemy_pkmn['Card Type']):
        continue
      is_condition_fulfilled = False
      break
    elif key == 'Prize Cards':
      if value == 'more':
        condition_string = condition_string + " and this card's player have more prize cards than the opposing card's player"
      continue  
    elif key == 'Rule Box':
      rulebox_eligible = ['ex', 'V', 'VMAX', 'VSTAR']
      for pkmn_card_type in ast.literal_eval(pkmn_data['Card Type']):
        if pkmn_card_type in rulebox_eligible:
          if value == 'None':
            is_condition_fulfilled = False
            break
      if is_condition_fulfilled: 
        continue
      else:
        break
    elif key == 'Evolution':
      if value != pkmn_data['Evolution Stage']:
        is_condition_fulfilled = False
        break
      continue
    elif key == 'Type':
      if value != pkmn_data['Type']:
        is_condition_fulfilled = False
        break
      continue
    elif key == 'Enemy Pkmn Type':
      if not isinstance(enemy_pkmn, pd.Series):
        is_condition_fulfilled = False
        break

      if value != enemy_pkmn['Type']:
        is_condition_fulfilled = False
        break
      continue
    elif key == 'Lost Zone Min Cards':
      is_condition_fulfilled = True
      condition_string = condition_string + f' and you have at least {value} cards in your Lost Zone'
    else:
      raise ValueError('key not found')
  
  return (is_condition_fulfilled, condition_string)

# finds all pokemon that one shot a certain pokemon
def calc_one_shot(pkmn_data, all_pkmn_data):
  # Array of dictionaries, each dictionary has all one shots for one pokemon
  # pkmn_name: pkmn_name
  # pkmn_name_w_set: pkmn_name_w_set
  # pkmn_hp: pkmn_hp
  # pkmn_weakness: pkmn_weakness
  # pkmn_resistance: pkmn_resistance
  # pkmn_getsoneshotby: 
  #     array of dictionaries, each dictionary containing:
  #     enemy_pkmn_name: enemy_pkmn_name
  #     enemy_pkmn_type: enemy_pkmn_type
  #     enemy_pkmn_move_name: enemy_pkmn_move_name
  #     enemy_pkmn_move_damage: enemy_pkmn_move_damage
  #     oneshot_string: oneshot_string

  # Order of loops:
  # 1. Enemy pkmn
  # 3. Enemy pkmn move
  # 3. Offensive (enemy pkmn) poketool
  # 4. Offensive supporter
  # 5. Offensive stadium
  # 6. Defensive (pkmn) poketool
  # 7. Defensive supporter
  # 8. Defensive stadium
  # If an offensive poketool for a move oneshots regardless of the defensive item, copy the first oneshot of the offensive poketool, rename offensive poketool to "Any Poketool," and delete oneshot strings
  # If all offensive poketools have the same oneshots for a given move, copy all oneshots of one offensive poketool and rename offensive poketool to "Any Poketool," and delete oneshot strings

  offensive_poketools_df = pd.read_csv('offensive_poketools.csv')
  defensive_poketools_df = pd.read_csv('defensive_poketools.csv')
  offensive_supporters_df = pd.read_csv('offensive_supporters.csv')
  defensive_supporters_df = pd.read_csv('defensive_supporters.csv')
  
  cur_pkmn_one_shots = {}
  # print(pkmn_data)
  cur_pkmn_one_shots['Pkmn Name'] = pkmn_data['Name']
  cur_pkmn_one_shots['Pkmn Name w/ Set'] = pkmn_data['Name w/ Set']
  cur_pkmn_one_shots['Pkmn HP'] = pkmn_data['HP']
  cur_pkmn_one_shots['Pkmn Weakness'] = pkmn_data['Weakness']
  cur_pkmn_one_shots['Pkmn Resistance'] = pkmn_data['Resistance'] if pkmn_data['Resistance'] != 'nan' else "None"
  cur_pkmn_one_shots['Pkmn Gets One Shot By'] = []
  cur_pkmn_one_shots['Pkmn Eligible Defensive Items'] = []
  cur_pkmn_one_shots['Pkmn Eligible Defensive Supporters'] = []

  defensive_poketool_eligible_list = []
  for i in range(len(defensive_poketools_df)):
    defensive_poketool = defensive_poketools_df.iloc[i]
    if not isinstance(defensive_poketool['Condition'], float): # indicates nan, meaning no condition
      defensive_poketool_isEligible = can_use_card(pkmn_data, None, ast.literal_eval(defensive_poketool['Condition']))
      if defensive_poketool_isEligible[0] == True:
        cur_pkmn_one_shots['Pkmn Eligible Defensive Items'].append(defensive_poketool['Item Name'])
        defensive_poketool_eligible_list.append(defensive_poketool)
    else:
      cur_pkmn_one_shots['Pkmn Eligible Defensive Items'].append(defensive_poketool['Item Name'])
      defensive_poketool_eligible_list.append(defensive_poketool)
  
  defensive_supporter_eligible_list = []
  for i in range(len(defensive_supporters_df)):
    defensive_supporter = defensive_supporters_df.iloc[i]
    # print(defensive_supporter)
    # print(defensive_supporter['Condition'])
    if not isinstance(defensive_supporter['Condition'], float): # indicates nan, meaning no condition
      defensive_supporter_isEligible = can_use_card(pkmn_data, None, ast.literal_eval(defensive_supporter['Condition']))
      if defensive_supporter_isEligible[0] == True:
        cur_pkmn_one_shots['Pkmn Eligible Defensive Supporters'].append(defensive_supporter['Supporter Name'])
        defensive_supporter_eligible_list.append(defensive_supporter)
    else:
      cur_pkmn_one_shots['Pkmn Eligible Defensive Supporters'].append(defensive_supporter['Supporter Name'])
      defensive_supporter_eligible_list.append(defensive_supporter)

  for index, enemy_pkmn in all_pkmn_data.iterrows():
    
    # If enemy pokemon has same type as current pokemon weakness, damage x2
    # If enemy pokemon has same type as current pokemon resistsance, damage - 30
    # If damage dealt by any enemy pokemon move >= current pokemon HP, KO
    is_original_weakness = False
    is_original_resistance = False
    original_weakness_multiplier = 2
    original_resistance_sub = 30
  
    if pkmn_data['Weakness'] == enemy_pkmn['Type']:
      is_original_weakness = True
    elif pkmn_data['Resistance'] == enemy_pkmn['Type']:
      is_original_resistance = True
    enemy_pkmn_moves = ast.literal_eval(enemy_pkmn['Moves'])

    original_hp = pkmn_data['HP']
    original_retreat_cost = pkmn_data['Retreat Cost']

    offensive_poketool_eligible_list = []
    for j in range(len(offensive_poketools_df)):
      offensive_poketool = offensive_poketools_df.iloc[j]
      if not isinstance(offensive_poketool['Condition'], float): # indicates nan, meaning no condition
        offensive_poketool_isEligible = can_use_card(enemy_pkmn, pkmn_data, ast.literal_eval(offensive_poketool['Condition']))
        if offensive_poketool_isEligible[0] == True:
          offensive_poketool_eligible_list.append(offensive_poketool)
      else:
        offensive_poketool_eligible_list.append(offensive_poketool)

    # Iterate over every move, then for every move iterate over every item to check oneshot
    for j in range(len(enemy_pkmn_moves)):
      cur_one_shot_by = {}
      enemy_move = enemy_pkmn_moves[j]
      effective_offensive_poketool_oneshot_arr = []

      for p, defensive_supporter in enumerate(defensive_supporter_eligible_list):
        base_dmg_taken_sub = 0
        if defensive_supporter['Supporter Name'] == 'Fantina':
          base_dmg_taken_sub = base_dmg_taken_sub + 120

        for k in range(len(offensive_poketool_eligible_list)):
          offensive_poketool = offensive_poketool_eligible_list[k]
          dmg_dealt_add = 0
          weakness_multiplier = original_weakness_multiplier
          resistance_sub = original_resistance_sub

          if offensive_poketool['Item Name'] == 'Future Booster Energy Capsule':
            dmg_dealt_add = dmg_dealt_add + 20
          elif offensive_poketool['Item Name'] == 'Maximum Belt':
            dmg_dealt_add = dmg_dealt_add + 50
          elif offensive_poketool['Item Name'] == 'Choice Belt':
            dmg_dealt_add = dmg_dealt_add + 30
          elif offensive_poketool['Item Name'] == 'Defiance Band':
            dmg_dealt_add = dmg_dealt_add + 30
          elif offensive_poketool['Item Name'] == 'Vitality Band':
            dmg_dealt_add = dmg_dealt_add + 10
          elif offensive_poketool['Item Name'] == 'Supereffective Glasses':
            weakness_multiplier = 3
          elif offensive_poketool['Item Name'] == 'Cleansing Gloves':
            dmg_dealt_add = dmg_dealt_add + 30

          effective_against_defensive_poketool_arr = []
          effective_against_defensive_poketool_counter = 0
          for m, defensive_poketool in enumerate(defensive_poketool_eligible_list):
            is_special_condition_immune = False
            is_enemy_supporter_immune = False      
            is_weakness = is_original_weakness
            is_resistance = is_original_resistance
            hp = original_hp
            retreat_cost = original_retreat_cost
            dmg_taken_sub = base_dmg_taken_sub

            if defensive_poketool['Item Name'] == 'Ancient Booster Energy Capsule':
              is_special_condition_immune = True
              hp = hp + 60
            elif defensive_poketool['Item Name'] == 'Future Booster Energy Capsule':
              retreat_cost = 0 # dmg increase not a factor in use as a defensive tool
            elif defensive_poketool['Item Name'] == 'Hero\'s Cape':
              hp = hp + 100
            elif defensive_poketool['Item Name'] == 'Rescue Board':
              retreat_cost = retreat_cost - 1
            elif defensive_poketool['Item Name'] == 'Defiance Vest':
              dmg_taken_sub = dmg_taken_sub + 40
            elif defensive_poketool['Item Name'] == 'Luxurious Cape':
              hp = hp + 100
            elif defensive_poketool['Item Name'] == 'Big Air Balloon':
              retreat_cost = 0
            elif defensive_poketool['Item Name'] == 'Protective Goggles':
              is_weakness = False
            elif defensive_poketool['Item Name'] == 'Rigid Band':
              dmg_taken_sub = dmg_taken_sub + 30
            elif defensive_poketool['Item Name'] == 'Bravery Charm':
              hp = hp + 50
            elif defensive_poketool['Item Name'] == 'Rock Chestplate':
              dmg_taken_sub = dmg_taken_sub + 30
            elif defensive_poketool['Item Name'] == 'Leafy Camo Poncho':
              is_enemy_supporter_immune = True
            elif defensive_poketool['Item Name'] == 'Pot Helmet':
              dmg_taken_sub = dmg_taken_sub + 30
            
            damage = int(enemy_move['Move Damage']) + dmg_dealt_add if enemy_move['Move Damage'] != None else None
      
            if damage != None:
              if is_weakness:
                damage = damage * weakness_multiplier
              elif is_resistance:
                damage = damage - resistance_sub
              
              damage = damage - dmg_taken_sub

              if damage >= hp:
                cur_one_shot_by['Oneshot String 1'] = enemy_pkmn['Name'] + ' using ' + enemy_move['Move Name'] + ' with ' + offensive_poketool['Item Name'] + ' one shots ' + pkmn_data['Name'] + ' with ' + defensive_poketool['Item Name']
                if offensive_poketool['Item Name'] == 'Defiance Band':
                  cur_one_shot_by['Oneshot String 1'] = cur_one_shot_by['Oneshot String 1'] + " when the opposing pokemon's player has more prize cards remaining than this pokemon's player"
                
                cur_one_shot_by['Oneshot String 2'] = pkmn_data['Name'] + ' has ' + str(hp) + ' HP'
                #  Logic from inside to outside (presentation needs to be different depending on present/absent elements)
                #  1. "move does base_damage"
                #  2. "move does base_damage - dmg_taken_sub"
                #  3. "move does base_damage * weakness_multiplier"
                #  4. "move does base_damage * weakness_multiplier - dmg_taken_sub"
                #  5. "move does base_damage - resistance_sub"
                #  6. "move does base_damage - resistance_sub - dmg_taken_sub"
                #  7. "move does base_damage + damage_dealt_add"
                #  8. "move does base_damage + damage_dealt_add - dmg_taken_sub"
                #  9. "move does (base_damage + damage_dealt_add) * weakness_multiplier"
                #  10. "move does (base_damage + damage_dealt_add) * weakness_multiplier - dmg_taken_sub"
                #  11. "move does base_damage + damage_dealt_add - resistance_sub"
                #  12. "move does base_damage + damage_dealt_add - resistance_sub - dmg_taken_sub"
                base_damage_template = enemy_move['Move Name'] + ' does '
                if dmg_taken_sub == 0 and not is_weakness and not is_resistance: # case 1
                  cur_one_shot_by['Oneshot String 3'] = base_damage_template + str(damage) + ' damage'
                else: # cases 2-12
                  if dmg_dealt_add == 0: # cases 2-6
                    base_damage_template = base_damage_template + str(int(enemy_move['Move Damage']))
                  elif not is_weakness: # cases 7-8, 11-12
                    base_damage_template = base_damage_template + str(int(enemy_move['Move Damage'])) + ' + ' + str(dmg_dealt_add)
                  else: # cases 9-10
                    base_damage_template = base_damage_template + '(' + str(int(enemy_move['Move Damage'])) + ' + ' + str(dmg_dealt_add) + ')'
                
                  if is_weakness: # cases 3-4, 9-10
                    base_damage_template = base_damage_template + ' * ' + str(weakness_multiplier) 
                  elif is_resistance: # cases 5-6, 11-12
                    base_damage_template = base_damage_template + ' - ' + str(resistance_sub)
                
                  if dmg_taken_sub > 0: # cases 2, 4, 6, 8, 10, 12
                    base_damage_template = base_damage_template + ' - ' + str(dmg_taken_sub)
                
                  # all cases
                  cur_one_shot_by['Oneshot String 3'] = base_damage_template + ' = ' + str(damage) + ' damage'
                
                cur_one_shot_by['Enemy Pokemon Name'] = enemy_pkmn['Name']
                cur_one_shot_by['Enemy Pokemon Name w/ Set'] = enemy_pkmn['Name w/ Set']
                cur_one_shot_by['Enemy Pokemon Type'] = enemy_pkmn['Type']
                cur_one_shot_by['Enemy Pokemon Move Name'] = enemy_move['Move Name']
                cur_one_shot_by['Enemy Pokemon Move Damage'] = enemy_move['Move Damage']
                
                cur_one_shot_by['Poketool'] = defensive_poketool['Item Name']
                cur_one_shot_by['Enemy Pokemon Poketool'] = offensive_poketool['Item Name']
                
                cur_one_shot_by['Supporter'] = defensive_supporter['Supporter Name']
                new_dict = cur_one_shot_by.copy()
                effective_against_defensive_poketool_arr.append(new_dict)
                effective_against_defensive_poketool_counter = effective_against_defensive_poketool_counter + 1
          # if the current offensive poketool is effective against all defensive tools (only applies to one move)
          if effective_against_defensive_poketool_counter == len(defensive_poketool_eligible_list):
            merged_one_shot = effective_against_defensive_poketool_arr[0]
            merged_one_shot['Poketool'] = 'Any/No Poketool'
            merged_one_shot['Oneshot String 2'] = ''
            merged_one_shot['Oneshot String 3'] = ''
            effective_offensive_poketool_oneshot_arr.append(merged_one_shot)
          else:
            for index, potential_one_shot in enumerate(effective_against_defensive_poketool_arr):
              # print(potential_one_shot)
              effective_offensive_poketool_oneshot_arr.append(potential_one_shot)
      # if the length of effective offensive poketools is the length of the offensive poketool eligible list
      # - get the first poketool
      # - add all defensive poketools it oneshots to an array
      # if all remaining poketools oneshot exactly the same defensive poketools:
      # - change all offensive poketool names for the first poketool's oneshots to "Any Poketool"
      # - only add the first poketool's oneshots
      # else:
      # - add all oneshots normally
      if len(effective_offensive_poketool_oneshot_arr) > 0:
        first_effective_offensive_poketool_name = effective_offensive_poketool_oneshot_arr[0]['Enemy Pokemon Poketool']
        temp_effective_against_defensive_poketool_arr = []
        temp_effective_against_defensive_poketool_arr_validator_counter = 0
        for temp_one_shot in effective_offensive_poketool_oneshot_arr:
          if temp_one_shot['Enemy Pokemon Poketool'] == first_effective_offensive_poketool_name and temp_one_shot not in temp_effective_against_defensive_poketool_arr:
            temp_effective_against_defensive_poketool_arr.append(temp_one_shot)
          else:
            break
        confirmed_offensive_poketools = []
        cur_defensive_poketool_index = 0
        cur_offensive_poketool = first_effective_offensive_poketool_name
        for index, temp_one_shot in enumerate(effective_offensive_poketool_oneshot_arr):
          if temp_one_shot['Enemy Pokemon Poketool'] != cur_offensive_poketool:
            if cur_defensive_poketool_index == len(temp_effective_against_defensive_poketool_arr):
              confirmed_offensive_poketools.append(cur_offensive_poketool)
            cur_offensive_poketool = temp_one_shot['Enemy Pokemon Poketool']
            cur_defensive_poketool_index = 0
          if temp_one_shot['Enemy Pokemon Poketool'] == cur_offensive_poketool and cur_defensive_poketool_index < len(temp_effective_against_defensive_poketool_arr):
            if temp_one_shot['Poketool'] == temp_effective_against_defensive_poketool_arr[cur_defensive_poketool_index]['Poketool']:
              cur_defensive_poketool_index = cur_defensive_poketool_index + 1
            else: 
              cur_defensive_poketool_index = 99
          elif cur_defensive_poketool_index >= len(temp_effective_against_defensive_poketool_arr):
            cur_defensive_poketool_index = 99
          if index == len(effective_offensive_poketool_oneshot_arr) - 1:
            if cur_defensive_poketool_index == len(temp_effective_against_defensive_poketool_arr):
              confirmed_offensive_poketools.append(cur_offensive_poketool)
        
        is_summarize_offensive_poketools = True
        for i in range(len(confirmed_offensive_poketools)):
          if confirmed_offensive_poketools[i] != offensive_poketool_eligible_list[i]['Item Name']:
            is_summarize_offensive_poketools = False
            break

        if is_summarize_offensive_poketools:
          for i in temp_effective_against_defensive_poketool_arr:
            i['Enemy Pokemon Poketool'] = 'Any/No Poketool'
            i['Oneshot String 2'] = ''
            i['Oneshot String 3'] = ''
            cur_pkmn_one_shots['Pkmn Gets One Shot By'].append(i)
        else:
          for i in effective_offensive_poketool_oneshot_arr:
            cur_pkmn_one_shots['Pkmn Gets One Shot By'].append(i)


        # Iterate over all other poketools. If the pokemon or move changes and we haven
        cur_enemy_pokemon = effective_offensive_poketool_oneshot_arr[0]['Enemy Pokemon Name']
        cur_enemy_move = effective_offensive_poketool_oneshot_arr[0]['Enemy Pokemon Move Name']
          
      
  return cur_pkmn_one_shots

def format_img_num(num):
    if 1 <= num <= 9:
        return f"00{num}"
    elif 10 <= num <= 99:
        return f"0{num}"
    elif 100 <= num <= 999:
        return str(num)
    else:
        return "Number out of range"

def remove_text_between_strings(input_string, start_string, end_string):
    pattern = re.compile(re.escape(start_string) + '.*?' + re.escape(end_string), re.DOTALL)
    return re.sub(pattern, f'{start_string}{end_string}', input_string)

def file_processing(pkmn_one_shots, expansion_no, poke_no):
  subdirectory_name = expansion_two_letters_arr[expansion_no]
  expansion_name = expansion_name_arr[expansion_no]
  expansion_img_prefix = expansion_img_prefix_arr[expansion_no]

  if len(pkmn_one_shots[0]) != 2:
    keys = list(pkmn_one_shots[0].keys())

    # with open('calc_data.csv', 'w', newline='') as csvfile:
    #   # Create a CSV writer object
    #   writer = csv.DictWriter(csvfile, fieldnames=keys)
    #   # Write the header row
    #   writer.writeheader()
    #   # Write each dictionary as a row in the CSV
    #   for item in pkmn_one_shots:
    #     writer.writerow(item)

    # csv.field_size_limit(1000000000000000)
    # with open('calc_data.csv', newline='') as csvfile:
    #   reader = csv.DictReader(csvfile)
    #   data = [row for row in reader]  # List of dictionaries  
    
    # with open('temp.json', 'w', newline='') as jsonfile:
    #   json.dump(data, jsonfile, indent=4)  # Pretty-printed JSON output
    
    # file = open('temp.json', 'r')
    # json_content = file.read()
    # updated_json_content = json_content.replace("'", '"')
    # updated_json_content = updated_json_content.replace('\\"', '"')
    # updated_json_content = updated_json_content[1:-1]
    # updated_json_content = updated_json_content.replace('pokemon"s', "pokemon's")
    # updated_json_content = updated_json_content.replace('Hero"s Cape', "Hero's Cape")
    # # Use sub to perform the replacement with capture groups
    # updated_json_content = re.sub(r'"\[{(.*?)}\]"', r'[{ \1 }]', updated_json_content)

    # with open('temp.json', 'w', newline='') as jsonfile:
    #   jsonfile.write(updated_json_content)  # Pretty-printed JSON output

    # get the opposing pokemon name
    # find if there are any duplicate entries for opposing pokemon
    # - if there are, then have a rowspan for the first row and none of that column for the remaining elements
    # - if there aren't, then just put one row
    # rest of finds are all limited from the beginning to the end of one pokemon's entries
    # find if there are any duplicate entries for opposing pokemon's poketools
    # - if there are, then find the amount of duplicates, then have a rowspan for the first occuring row and none of that column for the corresponding rows
    # repeat this for pkmn poketool, move, etc.
    # ensure that merged rows don't overlap past opposing pokemon name and that counters are reset between opposing pokemon
    table_row_template = ""
    # print(pkmn_one_shots[0]['Pkmn Gets One Shot By'])

    cur_enemy_pkmn_skip_until_index = 0
    cur_enemy_poketool_skip_until_index = 0
    cur_enemy_pkmn_move_skip_until_index = 0
    cur_poketool_skip_until_index = 0
    cur_oneshot_skip_until_index = 0

    is_cur_enemy_pkmn_color1 = True
    is_cur_enemy_poketool_color1 = True
    is_cur_enemy_pkmn_move_color1 = True
    is_cur_poketool_color1 = True
    is_cur_oneshot_color1 = True

    for index, cur_one_shot in enumerate(pkmn_one_shots[0]['Pkmn Gets One Shot By']):
      cur_table_row_template = "<tr>"

      cur_enemy_pkmn = cur_one_shot['Enemy Pokemon Name w/ Set']
      cur_enemy_poketool = cur_one_shot['Enemy Pokemon Poketool']
      cur_poketool = cur_one_shot['Poketool']
      cur_enemy_pkmn_move = cur_one_shot['Enemy Pokemon Move Name']
      cur_oneshot2 = cur_one_shot['Oneshot String 2']
      cur_oneshot3 = cur_one_shot['Oneshot String 3']
      
      enemy_pkmn_name_template = '<td>' + cur_enemy_pkmn + '</td>'
      enemy_poketool_template = '<td>' + cur_enemy_poketool + '</td>'
      poketool_template = '<td>' + cur_poketool + '</td>'
      enemy_pkmn_move_template = '<td>' + cur_enemy_pkmn_move + '</td>'
      
      # Example: 3 ways for Scyther to one shot Scyther
      # expected output is '<td rowspan=3>Scyther</td>' and the next check is skipped until...
      # index=3 if index=0
      # index=4 if index=1
      # but index 0 always needs to be checked

      ####################################### BEGIN CURRENT POKEMON NAME CHECKS ##############################################
      if index >= cur_enemy_pkmn_skip_until_index:
        cur_enemy_pkmn_counter = 0
        for index2, one_shot2 in enumerate(pkmn_one_shots[0]['Pkmn Gets One Shot By'][index:], index): # find duplicate entries
          if one_shot2['Enemy Pokemon Name w/ Set'] == cur_enemy_pkmn:
            cur_enemy_pkmn_counter = cur_enemy_pkmn_counter + 1
          else:
            break
        cur_enemy_pkmn_skip_until_index = cur_enemy_pkmn_skip_until_index + cur_enemy_pkmn_counter

        if is_cur_enemy_pkmn_color1:
          enemy_pkmn_name_template = '<td class="table_row_color1" rowspan=' + str(cur_enemy_pkmn_counter) + '>' + cur_enemy_pkmn + '</td>'
          is_cur_enemy_pkmn_color1 = False
        else:
          enemy_pkmn_name_template = '<td class="table_row_color2" rowspan=' + str(cur_enemy_pkmn_counter) + '>' + cur_enemy_pkmn + '</td>'
          is_cur_enemy_pkmn_color1 = True
        cur_table_row_template = cur_table_row_template + enemy_pkmn_name_template
      ####################################### END CURRENT POKEMON NAME CHECKS ################################################
      
      ####################################### BEGIN CURRENT ENEMY POKEMON MOVE NAME CHECKS ###################################
      if index >= cur_enemy_pkmn_move_skip_until_index:
        cur_enemy_pkmn_move_counter = 0
        for index2, one_shot2 in enumerate(pkmn_one_shots[0]['Pkmn Gets One Shot By'][index:], index): # find duplicate entries
          if one_shot2['Enemy Pokemon Move Name'] == cur_enemy_pkmn_move and index2 < cur_enemy_pkmn_skip_until_index:
            cur_enemy_pkmn_move_counter = cur_enemy_pkmn_move_counter + 1
          else:
            break
        cur_enemy_pkmn_move_skip_until_index = cur_enemy_pkmn_move_skip_until_index + cur_enemy_pkmn_move_counter

        if is_cur_enemy_pkmn_move_color1:
          enemy_pkmn_move_template = '<td class="table_row_color1" rowspan=' + str(cur_enemy_pkmn_move_counter) + '>' + cur_enemy_pkmn_move + '</td>'
          is_cur_enemy_pkmn_move_color1 = False
        else:
          enemy_pkmn_move_template = '<td class="table_row_color2" rowspan=' + str(cur_enemy_pkmn_move_counter) + '>' + cur_enemy_pkmn_move + '</td>'
          is_cur_enemy_pkmn_move_color1 = True
        cur_table_row_template = cur_table_row_template + enemy_pkmn_move_template
      ####################################### END CURRENT ENEMY POKEMON MOVE NAME CHECKS #####################################

      ####################################### BEGIN CURRENT ENEMY POKETOOL NAME CHECKS #######################################
      if index >= cur_enemy_poketool_skip_until_index:
        cur_enemy_poketool_counter = 0
        for index2, one_shot2 in enumerate(pkmn_one_shots[0]['Pkmn Gets One Shot By'][index:], index): # find duplicate entries
          if one_shot2['Enemy Pokemon Poketool'] == cur_enemy_poketool and index2 < cur_enemy_pkmn_skip_until_index:
            cur_enemy_poketool_counter = cur_enemy_poketool_counter + 1
          else:
            break
        cur_enemy_poketool_skip_until_index = cur_enemy_poketool_skip_until_index + cur_enemy_poketool_counter

        if is_cur_enemy_poketool_color1:
          enemy_poketool_template = '<td class="table_row_color1" rowspan=' + str(cur_enemy_poketool_counter) + '>' + cur_enemy_poketool + '</td>'
          is_cur_enemy_poketool_color1 = False
        else:
          enemy_poketool_template = '<td class="table_row_color2" rowspan=' + str(cur_enemy_poketool_counter) + '>' + cur_enemy_poketool + '</td>'
          is_cur_enemy_poketool_color1 = True
        cur_table_row_template = cur_table_row_template + enemy_poketool_template
      ####################################### END CURRENT ENEMY POKETOOL NAME CHECKS #########################################

      ####################################### BEGIN CURRENT POKETOOL NAME CHECKS #############################################
      if index >= cur_poketool_skip_until_index:
        cur_poketool_counter = 0
        for index2, one_shot2 in enumerate(pkmn_one_shots[0]['Pkmn Gets One Shot By'][index:], index): # find duplicate entries
          if one_shot2['Poketool'] == cur_poketool and index2 < cur_enemy_pkmn_skip_until_index:
            cur_poketool_counter = cur_poketool_counter + 1
          else:
            break
        cur_poketool_skip_until_index = cur_poketool_skip_until_index + cur_poketool_counter

        if is_cur_poketool_color1:
          poketool_template = '<td class="table_row_color1" rowspan=' + str(cur_poketool_counter) + '>' + cur_poketool + '</td>'
          is_cur_poketool_color1 = False
        else:
          poketool_template = '<td class="table_row_color2" rowspan=' + str(cur_poketool_counter) + '>' + cur_poketool + '</td>'
          is_cur_poketool_color1 = True
        cur_table_row_template = cur_table_row_template + poketool_template
      ####################################### END CURRENT POKETOOL NAME CHECKS ###############################################

      ####################################### BEGIN ONESHOT CHECKS ###################################
      if index >= cur_oneshot_skip_until_index:
        cur_oneshot_counter = 0
        for index2, one_shot2 in enumerate(pkmn_one_shots[0]['Pkmn Gets One Shot By'][index:], index): # find duplicate entries
          if one_shot2['Oneshot String 2'] == cur_oneshot2 and one_shot2['Oneshot String 3'] == cur_oneshot3 and index2 < cur_enemy_pkmn_skip_until_index:
            cur_oneshot_counter = cur_oneshot_counter + 1
          else:
            break
        cur_oneshot_skip_until_index = cur_oneshot_skip_until_index + cur_oneshot_counter

        if is_cur_oneshot_color1:
          if len(cur_oneshot2) > 0:
            oneshot_template = '<td class="table_row_color1" rowspan=' + str(cur_oneshot_counter) + '>' + cur_oneshot2 + '. ' + cur_oneshot3 + '.</td>'
          else:
            oneshot_template = '<td class="table_row_color1" rowspan=' + str(cur_oneshot_counter) + '></td>'
          is_cur_oneshot_color1 = False
        else:
          if len(cur_oneshot2) > 0:
            oneshot_template = '<td class="table_row_color2" rowspan=' + str(cur_oneshot_counter) + '>' + cur_oneshot2 + '. ' + cur_oneshot3 + '.</td>'
          else:
            oneshot_template = '<td class="table_row_color2" rowspan=' + str(cur_oneshot_counter) + '></td>'
          is_cur_oneshot_color1 = True
        cur_table_row_template = cur_table_row_template + oneshot_template
      ####################################### END ONESHOT CHECKS #####################################
      
      cur_table_row_template = cur_table_row_template + '</tr>'
      table_row_template = table_row_template + cur_table_row_template
    
    file = open('template/template.html', 'r')
    html_template = file.read()
    updated_html_template = html_template.replace(f'../{expansion_two_letters_arr[expansion_no]}/index.html', 'index.html')
    updated_html_template = updated_html_template.replace('{pkmn_name_with_set}', pkmn_one_shots[0]['Pkmn Name w/ Set'])
    updated_html_template = updated_html_template.replace('{num}', str(poke_no + 1))
    updated_html_template = updated_html_template.replace('{img_prefix}', expansion_img_prefix)
    updated_html_template = updated_html_template.replace('{img_num}', format_img_num(poke_no + 1))
    updated_html_template = updated_html_template.replace('{pkmn_hp}', str(pkmn_one_shots[0]['Pkmn HP']))
    if isinstance(pkmn_one_shots[0]['Pkmn Weakness'], str):
      updated_html_template = updated_html_template.replace('{pkmn_weakness}', pkmn_one_shots[0]['Pkmn Weakness'])
    else:
      updated_html_template = updated_html_template.replace('{pkmn_weakness}', 'None')
    if isinstance(pkmn_one_shots[0]['Pkmn Resistance'], str):
      updated_html_template = updated_html_template.replace('{pkmn_resistance}', pkmn_one_shots[0]['Pkmn Resistance'])
    else:
      updated_html_template = updated_html_template.replace('{pkmn_resistance}', 'None')

    effective_defensive_items_template = ''
    for index, effective_defense_item in enumerate(pkmn_one_shots[0]['Pkmn Eligible Defensive Items']):
      if index % 2 == 0:
        effective_defensive_items_template = effective_defensive_items_template + '<tr><td class="table_row_color2">' + effective_defense_item + '</td></tr>'
      else:
        effective_defensive_items_template = effective_defensive_items_template + '<tr><td class="table_row_color1">' + effective_defense_item + '</td></tr>'
    updated_html_template = updated_html_template.replace('{effective_defensive_items}', effective_defensive_items_template)
    updated_html_template = updated_html_template.replace('<td class="table_row_color2">Effective Defensive Poketools', '<td class="table_row_color2" rowspan=' + str(len(pkmn_one_shots[0]['Pkmn Eligible Defensive Items']) + 1) + '>Effective Defense Poketools (Total: ' + str(len(pkmn_one_shots[0]['Pkmn Eligible Defensive Items'])) + ')')

    first_table_index = updated_html_template.find('</table>')
    second_table_index = updated_html_template.find('</table>', first_table_index + 1)
    updated_html_template = updated_html_template[:second_table_index] + table_row_template + updated_html_template[second_table_index:]

    print(f'../website/{subdirectory_name}/' + str(poke_no + 1) + '.html')
    file = open(f'../website/{subdirectory_name}/' + str(poke_no + 1) + '.html', 'w')
    file.write(updated_html_template)
    
    # file = open('template/template.js', 'r')
    # js_template = file.read()
    # updated_js_template = js_template.replace('{data}', updated_json_content)

    # file = open('../website/tf/' + str(poke_no + 1) + '.js', 'w')
    # file.write(updated_js_template)

    file = open(f'../website/{subdirectory_name}/index.html', 'r')
    index_template = file.read()

    li_template = '<li class="mb-2"><a class="text-lg text-blue-500 hover:text-blue-700 underline" href="{num}.html">{pkmn_name_with_set}</a></li>'
    updated_li_template = li_template.replace('{num}', str(poke_no + 1))
    updated_li_template = updated_li_template.replace('{pkmn_name_with_set}', pkmn_one_shots[0]['Pkmn Name w/ Set'])

    insert_position = index_template.find('</ol')
    updated_index_template = index_template[:insert_position] + updated_li_template + index_template[insert_position:]
    updated_index_template = updated_index_template.replace('{expansion_name}', expansion_name)

    file = open(f'../website/{subdirectory_name}/index.html', 'w')
    file.write(updated_index_template)
  else:
    file = open('template/invalid_template.html', 'r')
    html_template = file.read()
    updated_html_template = html_template.replace('{pkmn_name_with_set}', pkmn_one_shots[0]['Pkmn Name w/ Set'])
    updated_html_template = updated_html_template.replace('{img_prefix}', expansion_img_prefix)
    updated_html_template = updated_html_template.replace('{img_num}', format_img_num(poke_no + 1))

    print(f'../website/{subdirectory_name}/' + str(poke_no + 1) + '.html')
    file = open(f'../website/{subdirectory_name}/' + str(poke_no + 1) + '.html', 'w')
    file.write(updated_html_template)
    
    # file = open('template/template.js', 'r')
    # js_template = file.read()
    # updated_js_template = js_template.replace('{data}', updated_json_content)

    # file = open('../website/tf/' + str(poke_no + 1) + '.js', 'w')
    # file.write(updated_js_template)

    file = open(f'../website/{subdirectory_name}/index.html', 'r')
    index_template = file.read()

    li_template = '<li class="mb-2"><a class="text-lg text-blue-500 hover:text-blue-700 underline" href="{num}.html">{pkmn_name_with_set}</a></li>'
    updated_li_template = li_template.replace('{num}', str(poke_no + 1))
    updated_li_template = updated_li_template.replace('{pkmn_name_with_set}', pkmn_one_shots[0]['Pkmn Name w/ Set'])

    insert_position = index_template.find('</ol')
    updated_index_template = index_template[:insert_position] + updated_li_template + index_template[insert_position:]
    updated_index_template = updated_index_template.replace('{expansion_name}', expansion_name)

    file = open(f'../website/{subdirectory_name}/index.html', 'w')
    file.write(updated_index_template)

# Read the CSV file into a DataFrame
if test == False:
  if os.path.exists('../website/index.html'):
    os.remove('../website/index.html')
  for index, expansion_csv_filename in enumerate(expansion_csv_filename_arr):
    if os.path.exists('../website/index.html'):
      file = open('../website/index.html', 'r')
    else:
      file = open('template/root_index_template.html', 'r')
    index_template = file.read()

    li_template = '<li class="mb-2"><a class="text-lg text-blue-500 hover:text-blue-700 underline" href="{expansion_two_letters}/index.html">{expansion_name}</a></li>'
    updated_li_template = li_template.replace('{expansion_two_letters}', expansion_two_letters_arr[index])
    updated_li_template = updated_li_template.replace('{expansion_name}', expansion_name_arr[index])

    insert_position = index_template.find('</ul>', index_template.find('</ul>') + len('</ul>'))
    updated_index_template = index_template[:insert_position] + updated_li_template + index_template[insert_position:]
    file = open('../website/index.html', 'w')
    file.write(updated_index_template)

    if os.path.exists(f'../website/{expansion_two_letters_arr[index]}/index.html'):
      os.remove(f'../website/{expansion_two_letters_arr[index]}/index.html')
      
    file = open('template/expansion_index_template.html', 'r')
    index_template = file.read()
    updated_index_template = index_template.replace(f'../{expansion_two_letters_arr[index]}/index.html', '#')
  
    file = open(f'../website/{expansion_two_letters_arr[index]}/index.html', 'w')
    file.write(updated_index_template)

    file = open(f'../website/{expansion_two_letters_arr[index]}/index.html', 'r')

    expansion_df = pd.read_csv(f'../data/{expansion_csv_filename}')
    expansion_two_letters = expansion_two_letters_arr[index]
    all_pkmn_df = pd.read_csv(f'../data/pkmn_data.csv')
    # Index(['Name', 'Name w/ Set', 'Evolution Stage', 'Previous Evolution',
    #       'Ability', 'HP', 'Type', 'Weakness', 'Resistance', 'Retreat Cost',
    #       'Moves', 'Card No', 'Card Mark', 'Card Rarity'],
    #      dtype='object')
    # column_names = expansion_df.columns
    # print(column_names)

    # Iterate through each row (using index or iterate over rows directly)
    # print(len(expansion_df))
    # for index, row in df.iterrows():
    #   # Access elements by column names
    #   print(row['Name'], row['Name w/ Set'], "...")
    for index2, row in expansion_df.iterrows():
      pkmn_one_shots = []
      if row['Card Mark'] != 'E':
        pkmn_one_shots.append(calc_one_shot(row, all_pkmn_df))
      else:
        pkmn_one_shots.append({
          "Pkmn Name": row["Name"],
          "Pkmn Name w/ Set": row["Name w/ Set"]
        })
      file_processing(pkmn_one_shots, index, index2)      
else:
  df = pd.read_csv(f'../data/tf.csv')
  for index, row in df.iterrows():
    if row['Name'] == 'Scyther':
      pkmn_one_shots = []
      pkmn_one_shots.append(calc_one_shot(row, df))
      file_processing(index, pkmn_one_shots)
      break