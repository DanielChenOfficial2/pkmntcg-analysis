import pandas as pd
import ast
import csv

test = False

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
  cur_pkmn_one_shots = {}
  cur_pkmn_one_shots['Pkmn Name'] = pkmn_data['Name']
  cur_pkmn_one_shots['Pkmn Name w/ Set'] = pkmn_data['Name w/ Set']
  cur_pkmn_one_shots['Pkmn HP'] = pkmn_data['HP']
  cur_pkmn_one_shots['Pkmn Weakness'] = pkmn_data['Weakness']
  cur_pkmn_one_shots['Pkmn Resistance'] = pkmn_data['Resistance']
  one_shot_by = []
  
  for index, enemy_pkmn in all_pkmn_data.iterrows():
    if pkmn_data['Name w/ Set'] == enemy_pkmn['Name w/ Set']:
      continue
    
    # If enemy pokemon has same type as current pokemon weakness, damage x2
    # If enemy pokemon has same type as current pokemon resistsance, damage - 30
    # If damage dealt by any enemy pokemon move >= current pokemon HP, KO
    is_weakness = False
    is_resistance = False
    if pkmn_data['Weakness'] == enemy_pkmn['Type']:
      is_weakness = True
    elif pkmn_data['Resistance'] == enemy_pkmn['Type']:
      is_resistance = True
    enemy_pkmn_moves = ast.literal_eval(enemy_pkmn['Moves'])

    for j in range(len(enemy_pkmn_moves)):
      cur_one_shot_by = {}
      enemy_move = enemy_pkmn_moves[j]
      
      damage = int(enemy_move['Move Damage']) if enemy_move['Move Damage'] != None else None
      if damage != None:
        if is_weakness:
          damage = damage * 2
        elif is_resistance:
          damage = damage - 30

        if damage >= pkmn_data['HP']:
          cur_one_shot_by['Oneshot String 1'] = enemy_pkmn['Name'] + ' one shots ' + pkmn_data['Name'] + ' with ' + enemy_move['Move Name']
          cur_one_shot_by['Oneshot String 2'] = pkmn_data['Name'] + ' has ' + str(pkmn_data['HP']) + ' HP'
          # print(enemy_pkmn['Name'] + ' one shots ' + pkmn_data['Name'] + ' with ' + enemy_move['Move Name'])
          # print(pkmn_data['Name'] + ' has ' + str(pkmn_data['HP']) + ' HP')
          if is_weakness:
            # print(enemy_move['Move Name'] + ' does ' + enemy_move['Move Damage'] + ' * 2 = ' + str(int(enemy_move['Move Damage']) * 2) + ' damage')
            cur_one_shot_by['Oneshot String 3'] = enemy_move['Move Name'] + ' does ' + enemy_move['Move Damage'] + ' * 2 = ' + str(int(enemy_move['Move Damage']) * 2) + ' damage'
          elif is_resistance:
            # print(enemy_move['Move Name'] + ' does ' + enemy_move['Move Damage'] + ' - 30 = ' + str(int(enemy_move['Move Damage']) - 30) + ' damage')
            cur_one_shot_by['Oneshot String 3'] = enemy_move['Move Name'] + ' does ' + enemy_move['Move Damage'] + ' - 30 = ' + str(int(enemy_move['Move Damage']) - 30) + ' damage'
          else:
            # print(enemy_move['Move Name'] + ' does ' + enemy_move['Move Damage'] + ' damage')
            cur_one_shot_by['Oneshot String 3'] = enemy_move['Move Name'] + ' does ' + enemy_move['Move Damage'] + ' damage'
          # print('\n')
          
          cur_one_shot_by['Enemy Pokemon Name'] = enemy_pkmn['Name']
          cur_one_shot_by['Enemy Pokemon Type'] = enemy_pkmn['Type']
          cur_one_shot_by['Enemy Pokemon Move Name'] = enemy_move['Move Name']
          cur_one_shot_by['Enemy Pokemon Move Damage'] = enemy_move['Move Damage']

          one_shot_by.append(cur_one_shot_by)
  cur_pkmn_one_shots['Pkmn Gets One Shot By'] = one_shot_by  
  print(cur_pkmn_one_shots)
  return cur_pkmn_one_shots

print("CSV file created successfully: pokemon_data.csv")

# Read the CSV file into a DataFrame
df = pd.read_csv('../webscrape/pokemon_data.csv')

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
    # print(row['Name'])
    if row['Name'] == 'Mr. Mime':
      pkmn_one_shots.append(calc_one_shot(row, df))

keys = list(pkmn_one_shots[0].keys())
with open('pokemon_data.csv', 'w', newline='') as csvfile:
  # Create a CSV writer object
  writer = csv.DictWriter(csvfile, fieldnames=keys)
  # Write the header row
  writer.writeheader()
  # Write each dictionary as a row in the CSV
  for item in pkmn_one_shots:
    writer.writerow(item)  