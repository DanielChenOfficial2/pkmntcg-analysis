import pandas as pd
import ast
import csv
import json
import math

test = True

def can_use_poketool(pkmn_data, enemy_pkmn, poketool_condition):
  is_condition_fulfilled = True
  condition_string = ''
  for key, value in poketool_condition.items():
    if key == 'Pkmn Card Type':
      
      # print(pkmn_data['Name'])
      # print(poketool_condition)
      # print(pkmn_data['Card Type'])
      # print('\n')
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
        condition_string = condition_string + ' and you have more prize cards than your opponent'
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
  offensive_poketools_df = pd.read_csv('offensive_poketools.csv')
  defensive_poketools_df = pd.read_csv('defensive_poketools.csv')
  
  cur_pkmn_one_shots = {}
  cur_pkmn_one_shots['Pkmn Name'] = pkmn_data['Name']
  cur_pkmn_one_shots['Pkmn Name w/ Set'] = pkmn_data['Name w/ Set']
  cur_pkmn_one_shots['Pkmn HP'] = pkmn_data['HP']
  cur_pkmn_one_shots['Pkmn Weakness'] = pkmn_data['Weakness']
  cur_pkmn_one_shots['Pkmn Resistance'] = pkmn_data['Resistance'] if pkmn_data['Resistance'] != 'nan' else "None"
  cur_pkmn_one_shots['Pkmn Gets One Shot By'] = []
  # cur_pkmn_one_shots['Pkmn Eligible Defensive Items'] = []

  defensive_poketool_eligible_list = []
  for i in range(len(defensive_poketools_df)):
    defensive_poketool = defensive_poketools_df.iloc[i]
    if not isinstance(defensive_poketool['Condition'], float): # indicates nan, meaning no condition
      defensive_poketool_isEligible = can_use_poketool(pkmn_data, None, ast.literal_eval(defensive_poketool['Condition']))
      if defensive_poketool_isEligible[0] == True:
        # cur_pkmn_one_shots['Pkmn Eligible Defensive Items'].append(defensive_poketool['Item Name'])
        defensive_poketool_eligible_list.append(defensive_poketool)
    else:
      # cur_pkmn_one_shots['Pkmn Eligible Defensive Items'].append(defensive_poketool['Item Name'])
      defensive_poketool_eligible_list.append(defensive_poketool)
  # print(cur_pkmn_one_shots['Pkmn Name'])
  # print(cur_pkmn_one_shots['Pkmn Eligible Defensive Items'])
  # print('\n')
  one_shot_by = []
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
        offensive_poketool_isEligible = can_use_poketool(enemy_pkmn, pkmn_data, ast.literal_eval(offensive_poketool['Condition']))
        if offensive_poketool_isEligible[0] == True:
          offensive_poketool_eligible_list.append(offensive_poketool)
      else:
        offensive_poketool_eligible_list.append(offensive_poketool)
      
    # print(enemy_pkmn['Name'])
    # print(offensive_poketool_eligible_list)
    # print('\n')

    # Iterate over every move, then for every move iterate over every item to check oneshot
    for j in range(len(enemy_pkmn_moves)):
      cur_one_shot_by = {}
      enemy_move = enemy_pkmn_moves[j]

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
        # is_condition_fulfilled = True
        # condition_string = ''
        # if poketool['Item Name'] != 'No Item':
        #   if not isinstance(poketool['Condition'], float): # indicates nan, meaning no condition
            # print(poketool['Condition'])
            # print(can_equip_item(pkmn_data, enemy_pkmn, condition))
        for m, defensive_poketool in enumerate(defensive_poketool_eligible_list):
          # print(offensive_poketool['Item Name'])
          # print(defensive_poketool['Item Name'])
          # print('\n')
          is_special_condition_immune = False
          is_enemy_supporter_immune = False      
          is_weakness = is_original_weakness
          is_resistance = is_original_resistance
          hp = original_hp
          retreat_cost = original_retreat_cost
          dmg_taken_sub = 0

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
            dmg_taken_sub = 40
          elif defensive_poketool['Item Name'] == 'Luxurious Cape':
            hp = hp + 100
          elif defensive_poketool['Item Name'] == 'Big Air Balloon':
            retreat_cost = 0
          elif defensive_poketool['Item Name'] == 'Protective Goggles':
            is_weakness = False
          elif defensive_poketool['Item Name'] == 'Rigid Band':
            dmg_taken_sub = 30
          elif defensive_poketool['Item Name'] == 'Bravery Charm':
            hp = hp + 50
          elif defensive_poketool['Item Name'] == 'Rock Chestplate':
            dmg_taken_sub = 30
          elif defensive_poketool['Item Name'] == 'Leafy Camo Poncho':
            is_enemy_supporter_immune = True
          elif defensive_poketool['Item Name'] == 'Pot Helmet':
            dmg_taken_sub = 30
  
          damage = int(enemy_move['Move Damage']) - dmg_taken_sub + dmg_dealt_add if enemy_move['Move Damage'] != None else None
          if damage != None:
            if is_weakness:
              damage = damage * weakness_multiplier
            elif is_resistance:
              damage = damage - resistance_sub

            if damage >= hp:
              cur_one_shot_by['Oneshot String 1'] = enemy_pkmn['Name'] + ' using ' + enemy_move['Move Name'] + ' with ' + offensive_poketool['Item Name'] + ' one shots ' + pkmn_data['Name'] + ' with ' + defensive_poketool['Item Name']
              if offensive_poketool['Item Name'] == 'Defiance Band':
                cur_one_shot_by['Oneshot String 1'] = cur_one_shot_by['Oneshot String 1'] + " when the opposing pokemon's player has more prize cards remaining than this pokemon's player"
              
              cur_one_shot_by['Oneshot String 2'] = pkmn_data['Name'] + ' has ' + str(hp) + ' HP'
              # print(enemy_pkmn['Name'] + ' one shots ' + pkmn_data['Name'] + ' with ' + enemy_move['Move Name'])
              # print(pkmn_data['Name'] + ' has ' + str(pkmn_data['HP']) + ' HP')

              # Move name + 
              base_damage_template = enemy_move['Move Name'] + ' does '
              if dmg_taken_sub == 0:
                if dmg_dealt_add == 0:
                  # no damage taken or damage added
                  base_damage_template = base_damage_template + str(int(enemy_move['Move Damage']))
                else:
                  # no damage taken but damage added
                  base_damage_template = base_damage_template + '(' + str(int(enemy_move['Move Damage'])) + ' + ' + str(dmg_dealt_add) + ')'
              else:
                if dmg_dealt_add == 0:
                  # damage taken but no damage added
                  base_damage_template = base_damage_template + '(' + str(int(enemy_move['Move Damage'])) + ' - ' + str(dmg_taken_sub) + ')'
                else:
                  # damage taken and damage added
                  base_damage_template = base_damage_template + '(' + str(int(enemy_move['Move Damage'])) + ' + ' + str(dmg_dealt_add) + ' - ' + str(dmg_taken_sub) + ')'

              if is_weakness:
                cur_one_shot_by['Oneshot String 3'] = base_damage_template + ' * ' + str(weakness_multiplier) + ' = ' + str(((int(enemy_move['Move Damage']) + dmg_dealt_add - dmg_taken_sub) * weakness_multiplier)) + ' damage'
              elif is_resistance:
                cur_one_shot_by['Oneshot String 3'] = base_damage_template + ' - ' + str(resistance_sub) + ' = ' + str((int(enemy_move['Move Damage']) + dmg_dealt_add - dmg_taken_sub) - resistance_sub) + ' damage'
              else:
                if dmg_dealt_add > 0 or dmg_taken_sub > 0:
                  cur_one_shot_by['Oneshot String 3'] = base_damage_template + ' = ' +  str((int(enemy_move['Move Damage']) + dmg_dealt_add - dmg_taken_sub)) + ' damage'
                else:
                  cur_one_shot_by['Oneshot String 3'] = base_damage_template + ' damage'
              # print('\n')
              
              cur_one_shot_by['Enemy Pokemon Name'] = enemy_pkmn['Name']
              cur_one_shot_by['Enemy Pokemon Type'] = enemy_pkmn['Type']
              cur_one_shot_by['Enemy Pokemon Move Name'] = enemy_move['Move Name']
              cur_one_shot_by['Enemy Pokemon Move Damage'] = enemy_move['Move Damage']
              
              cur_one_shot_by['Poketool'] = defensive_poketool['Item Name']
              cur_one_shot_by['Enemy Poketool'] = offensive_poketool['Item Name']
              # print(cur_one_shot_by['Oneshot String 1'])
              # print(cur_one_shot_by['Oneshot String 2'])
              # print(cur_one_shot_by['Oneshot String 3'])
              # print('\n')
              new_dict = cur_one_shot_by.copy()
              cur_pkmn_one_shots['Pkmn Gets One Shot By'].append(new_dict)
              # print(cur_pkmn_one_shots['Pkmn Gets One Shot By'])
              # print(offensive_poketool['Item Name'])
              # print(defensive_poketool['Item Name'])
              # print(cur_one_shot_by['Oneshot String 1'])
              print('\n')
  # print(one_shot_by)        
  # print(cur_pkmn_one_shots)
  # print('\n')
  return cur_pkmn_one_shots

# Read the CSV file into a DataFrame
df = pd.read_csv('../webscraper/pkmn_data.csv')

# Index(['Name', 'Name w/ Set', 'Evolution Stage', 'Previous Evolution',
#       'Ability', 'HP', 'Type', 'Weakness', 'Resistance', 'Retreat Cost',
#       'Moves', 'Card No', 'Card Mark', 'Card Rarity'],
#      dtype='object')
column_names = df.columns

# Iterate through each row (using index or iterate over rows directly)
# print(len(df))
# for index, row in df.iterrows():
#   # Access elements by column names
#   print(row['Name'], row['Name w/ Set'], "...")

pkmn_one_shots = []
if test == False:
  for index, row in df.iterrows():
    pkmn_one_shots.append(calc_one_shot(row, df))
else:
  for index, row in df.iterrows():
    if row['Name'] == 'Scyther':
      pkmn_one_shots.append(calc_one_shot(row, df))
      break

keys = list(pkmn_one_shots[0].keys())

with open('calc_data.csv', 'w', newline='') as csvfile:
  # Create a CSV writer object
  writer = csv.DictWriter(csvfile, fieldnames=keys)
  # Write the header row
  writer.writeheader()
  # Write each dictionary as a row in the CSV
  for item in pkmn_one_shots:
    writer.writerow(item)

csv.field_size_limit(1000000000000000)
with open('calc_data.csv', newline='') as csvfile:
  reader = csv.DictReader(csvfile)
  data = [row for row in reader]  # List of dictionaries  

with open('scyther.json', 'w', newline='') as jsonfile:
  json.dump(data, jsonfile, indent=4)  # Pretty-printed JSON output

# with open('pkmn_data2.json', "w") as file:
#   file.write(str(pkmn_one_shots).replace("'", '"'))

# print(pkmn_one_shots)