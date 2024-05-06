const data = {data};

window.addEventListener('load', () => {
  const hpVal = document.getElementById('hpVal');
  hpVal.innerHTML = data['Pkmn HP'];

  const weaknessVal = document.getElementById('weaknessVal');
  if (data['Pkmn Weakness'] = 'nan') {
    weaknessVal.innerHTML = "None";
  }
  else {
    weaknessVal.innerHTML = data['Pkmn Weakness'];
  }
  
  const resistanceVal = document.getElementById('resistanceVal');
  if (data['Pkmn Resistance'] = 'nan') {
    resistanceVal.innerHTML = "None";
  }
  else {
    resistanceVal.innerHTML = data['Pkmn Resistance'];
  }

  const oneShotBy = document.getElementById('oneShotBy');
  for (let i = 0; i < data['Pkmn Gets One Shot By'].length; i++) {
    // opposing pkmn, opposing pkmn poketool, curr pkmn poketool, move, damage calc
    const newRow = oneShotBy.insertRow();

    const enemyPkmn = newRow.insertCell();
    enemyPkmn.innerHTML = data['Pkmn Gets One Shot By'][i]['Enemy Pokemon Name w/ Set'];
    
    const enemyPkmnPoketool = newRow.insertCell();
    if (data['Pkmn Gets One Shot By'][i]['Enemy Poketool'] !== 'No Poketool') {
      enemyPkmnPoketool.innerHTML = data['Pkmn Gets One Shot By'][i]['Enemy Poketool'];
    }
    else {
      enemyPkmnPoketool.innerHTML = 'None'
    }
    
    const poketool = newRow.insertCell();
    if (data['Pkmn Gets One Shot By'][i]['Poketool'] !== 'No Poketool') {
      poketool.innerHTML = data['Pkmn Gets One Shot By'][i]['Poketool'];
    }
    else {
      poketool.innerHTML = 'None'
    }
    
    const move = newRow.insertCell();
    move.innerHTML = data['Pkmn Gets One Shot By'][i]['Enemy Pokemon Move Name'];
    
    const calc = newRow.insertCell();
    calc.innerHTML = data['Pkmn Gets One Shot By'][i]['Oneshot String 2'] + '. ' + data['Pkmn Gets One Shot By'][i]['Oneshot String 3'];
  }
})