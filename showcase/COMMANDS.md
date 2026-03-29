# Ember Depths — Generation Commands

Every asset in this showcase was generated with the commands below. All outputs go to `showcase/assets/`.

## Characters

```bash
# Hero — armored knight with flaming sword
pixel-magic generate \
  --name ember-knight \
  --description "medieval knight in dark steel armor with orange flame accents, wielding a flaming longsword, red cape" \
  --directions 4 --tiles 1 \
  --sizes 32,64 \
  --output-dir showcase/assets/characters

# Hero animations
pixel-magic animate \
  --name ember-knight \
  --animation walk --frames 6 --platform \
  --output-dir showcase/assets/characters

pixel-magic animate \
  --name ember-knight \
  --animation idle --frames 4 --platform \
  --output-dir showcase/assets/characters

pixel-magic animate \
  --name ember-knight \
  --animation attack --frames 5 --platform --no-loop \
  --output-dir showcase/assets/characters

# Forest goblin (green skin — use blue chromakey)
pixel-magic generate \
  --name forest-goblin \
  --description "small green-skinned goblin with a wooden club, leaf hat, tattered brown loincloth" \
  --directions 4 --chromakey blue \
  --sizes 32,64 \
  --output-dir showcase/assets/characters

# Cave bat
pixel-magic generate \
  --name cave-bat \
  --description "large purple bat with glowing red eyes, leathery wings spread wide, fangs visible" \
  --directions 4 \
  --sizes 32,64 \
  --output-dir showcase/assets/characters

# Fire imp
pixel-magic generate \
  --name fire-imp \
  --description "tiny red imp wreathed in orange flame, pointed horns, mischievous grin, holding a fireball" \
  --directions 4 \
  --sizes 32,64 \
  --output-dir showcase/assets/characters

# Lava dragon (large — 4-tile footprint)
pixel-magic generate \
  --name lava-dragon \
  --description "ancient red dragon with molten cracks glowing orange across its scales, massive wings, curled tail" \
  --directions 4 --tiles 4 \
  --sizes 64,128 \
  --output-dir showcase/assets/characters
```

## Tiles

```bash
# Forest ruins tileset
pixel-magic tile \
  --theme custom \
  --types "grass,moss stone,cracked path,water puddle,flowers,root-covered stone" \
  --style "16-bit SNES RPG style, overgrown ancient ruins" \
  --sizes 32,64 \
  --output-dir showcase/assets/tiles

# Cavern tileset
pixel-magic tile \
  --theme custom \
  --types "dark stone,crystal floor,wet stone,underground water,gravel,glowing moss" \
  --style "16-bit SNES RPG style, underground cave" \
  --sizes 32,64 \
  --output-dir showcase/assets/tiles

# Volcanic tileset
pixel-magic tile \
  --theme custom \
  --types "basalt,lava,cracked obsidian,ash,magma vein,cooled lava" \
  --style "16-bit SNES RPG style, volcanic hellscape" \
  --sizes 32,64 \
  --output-dir showcase/assets/tiles
```

## Objects

```bash
# Forest ruins objects
pixel-magic object \
  --preset custom \
  --names "broken pillar,vine archway,ancient chest,moss boulder,mushroom,overgrown statue" \
  --description "overgrown ancient ruins in a forest" \
  --sizes 32,64 \
  --output-dir showcase/assets/objects

# Cavern objects
pixel-magic object \
  --preset custom \
  --names "crystal cluster,stalactite,mine cart,mushroom patch,bones pile,cave torch" \
  --description "underground cave and abandoned mine" \
  --sizes 32,64 \
  --output-dir showcase/assets/objects

# Volcanic objects
pixel-magic object \
  --preset custom \
  --names "lava fountain,obsidian spike,fire brazier,dragon egg,charred tree,magma crystal" \
  --description "volcanic hellscape with molten lava" \
  --sizes 32,64 \
  --output-dir showcase/assets/objects

# Object animations
pixel-magic animate-object \
  --set custom --name "cave torch" --animation flicker --frames 5 \
  --output-dir showcase/assets/objects

pixel-magic animate-object \
  --set custom --name "vine archway" --animation sway --frames 5 \
  --output-dir showcase/assets/objects

pixel-magic animate-object \
  --set custom --name "lava fountain" --animation burn --frames 6 \
  --output-dir showcase/assets/objects
```

## Effects

```bash
# Combat effects
pixel-magic effect --name sword-slash --frames 5 --no-loop \
  --sizes 32,64 --output-dir showcase/assets/effects

pixel-magic effect --name fire-explosion --frames 6 --no-loop \
  --sizes 32,64 --output-dir showcase/assets/effects

# Magic effects (looping)
pixel-magic effect --name magic-shield --frames 6 --loop \
  --sizes 32,64 --output-dir showcase/assets/effects

pixel-magic effect --name healing-glow --frames 6 --loop \
  --sizes 32,64 --output-dir showcase/assets/effects

# Environmental effects
pixel-magic effect --name lava-bubble --frames 5 --loop \
  --sizes 32,64 --output-dir showcase/assets/effects

pixel-magic effect --name poison-cloud --frames 6 --loop \
  --sizes 32,64 --output-dir showcase/assets/effects
```
