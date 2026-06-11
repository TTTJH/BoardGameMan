# Eval Cases And Retrieval Outputs

???????????????????????? LLM ???????????????????????????????????? Top Sources ???

## Arydia: The Paths We Dare Tread

- Run time: 2026-06-03 12:19:05
- Pass: 1/8 (12%)
- Source hit: 75%
- Term coverage avg: 25%

### [FAIL] 当角色达到4级后，如何更换已装备的技能？多余的技能存放在哪里？

- Category: `action`
- Expected pages: `[15]`
- Found pages: `[15, 71, 51, 36, 19, 53, 17]`
- Source hit: `True`
- Term coverage: `0.00`
- Missing terms: `['Level 4', 'slots', "Exiles' Guild", 'tuckbox', 'equipped']`

Top sources:
1. Page `15`: [Page 15] [Section: Pathless Items: 1 1 1] gain 2 You. cannot exceed 55 your MAX +3. the Silent LVL your Character Estmor Card. Ceildar 77 6 • Track: Place (marker cubes) to track LVL cannot the exceed Nervous the MAX the, Hungry as set by the the iranuL 99 crO 7 • d20: Keep your d20 here LVL when you’re not the Silent the Plucky the I t e m s Enduring crO A…
2. Page `71`: [Page 71] [Section: Equipment Mat 8 Natural Rolls (Natural] Bonus Damage31, 32 Index / Index System Borders21 Interact Action.. Boss24 Inventory Buy Items (Armorer)17 Item Details Card Types12 Items (Pathless / Character Cards 6 Job Cards (Types Character Mat 6 Kae (Character Mat, Checks (d20 System)10 Key Cards Chests 8 KO’d (Adventure Cleared / Unexplored1…
3. Page `51`: [Page 51] [Section: KeywCorhdosmp Whip] a hit die and can cause • X: Move with X (e.g. 3 means move FOE-5 0 Giant Rat Boss Mob Rabid Rat 0 2 Bite 1 5 Bite 3 5 Frenzy Bite Frenzy 1 2 is drawn, there is a Boss fo+e1, and four Mob foes. The on its Grid card (“0”), so it activates first. There is Boss can’t afford their 3 Chomp+1 behavior, so behavior1, spe +ndi…

### [FAIL] 使用标记为免费、反应或持续（Free, Reaction, or Ongoing）的技能时，需要消耗行动标记吗？

- Category: `cost`
- Expected pages: `[57]`
- Found pages: `[57, 13, 33]`
- Source hit: `True`
- Term coverage: `0.33`
- Missing terms: `['Skills designated as Free', 'Reaction, or Ongoing']`

Top sources:
1. Page `57`: [Page 57] [Section: + 2. 10+ Take 18+ Actions] Exile These namuH After the Foe Turn, the active Resourceful player takes their Reaction Turn has 3 parts: After an exile rolls a d20: Pay to reroll, using the 1. Start Turn highest result instead. At the start of a turn, place your 2 Normal action action token in the ready area of your equipment of turn abiliti…
2. Page `57`: [Page 57] [Section: Reaction ] Trigger any start action. Practice iranuL • Free Actions: Shortbow Actions crO token to activate. To costs, then resolve be taken when no After resolving an action, have Lightheart different done taking Enduring actions, Reaction Action Req. Out of Combat or do not wish to take END 1 3 After being attacked: Pay to gain 2+ 1, Pa…
3. Page `13`: [Page 13] [Section: Free 3 Reaction] Shield party’s armor. the damage Shield Shout side and Mastered side. When you gain sits Learned side up until it is Mastered. Attack 1 Spin Attack 9 WAR-4 10 To Master: Starting skill. Take when you choose Path of Valor. 7 11 Sword Learned side Dodge Sharpen 3 Minor 4 H A 1 2 P u t o n a n a d j a c e n t w e a p o n. ta…

### [FAIL] 学习新技能时，前置技能需要装备并精通后才能学习吗？

- Category: `exception`
- Expected pages: `[13]`
- Found pages: `[71, 15, 17, 43, 13, 57]`
- Source hit: `True`
- Term coverage: `0.00`
- Missing terms: `['prerequisite skills', "don't need to be equipped", 'nor mastered', 'learned first']`

Top sources:
1. Page `71`: [Page 71] [Section: Equipment Mat 8 Natural Rolls (Natural] Bonus Damage31, 32 Index / Index System Borders21 Interact Action.. Boss24 Inventory Buy Items (Armorer)17 Item Details Card Types12 Items (Pathless / Character Cards 6 Job Cards (Types Character Mat 6 Kae (Character Mat, Checks (d20 System)10 Key Cards Chests 8 KO’d (Adventure Cleared / Unexplored1…
2. Page `15`: [Page 15] [Section: Pathless Items: 1 1 1] gain 2 You. cannot exceed 55 your MAX +3. the Silent LVL your Character Estmor Card. Ceildar 77 6 • Track: Place (marker cubes) to track LVL cannot the exceed Nervous the MAX the, Hungry as set by the the iranuL 99 crO 7 • d20: Keep your d20 here LVL when you’re not the Silent the Plucky the I t e m s Enduring crO A…
3. Page `17`: [Page 17] [Section: Practice Kunai] When using a skill: 5 • Durability 2+ 10+ 18+ Pay to reduce its cost represents how by up to 2. many Wear tokens this item can hold Shield Charge before becoming 1 2 6 Shield broken and needing Mystic direction. 4 5 repair. in your Reaction way, damage 6 • Worn them location: This denotes where you place or left. When usin…

### [FAIL] 学习新技能时，如果角色面板上没有空位，还能学习新技能吗？

- Category: `exception`
- Expected pages: `[13]`
- Found pages: `[16, 2, 57, 24, 25, 15, 72, 12]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['no open slots', 'unequip a skill', 'make room', 'new skill']`

Top sources:
1. Page `16`: [Page 16] [Section: REGELKARTEN - REF] REF-Karten befinden sich im Index. Pfadspezifische Karten befinden sich in der Tuckbox des jeweiligen Pfads.
2. Page `2`: [Page 2] [Section: Allgemeine Regeln 10] Inhaltsverzeichnis: Komponenten 2 Setup 4 Spielercharaktere (Exilanten) 6 Allgemeine Regeln 10 Kartentypen 12 Abenteuer 15 Weltkarten 16 Orte 18 Kampf 20 Feinde 24 Exilantenrunden 29 Metaregeln 33 Soundtrack 35 Credits 35 Glossar 36 Wenn Sie zum ersten Mal spielen, beginnen Sie mit der Kurzanleitung, die Ihnen hilft,…
3. Page `57`: [Page 57] [Section: Practice 1 Sneak 1 Practice Req. Backstab Bow] and/or any Noodler 2 DNE + 2 with an adjacent Mark Broadhead 1 Anthem of Vigor Scamp Minor R e q: L u t e 0 = 1 / 1 or PDraagcgtiecre Free permission. 2 +1 etuL LA llt ee x i l ge as in: 1 1 1 1 u 1 = 1 1 1 Place on Gutsy Dash = 1 2 When equip the item a fo e y o Req: u Tanto f o e is 1 Equip…

### [FAIL] 无路径物品和路径物品有什么区别？无路径物品可以被任何路径的角色使用吗？

- Category: `exception`
- Expected pages: `[15]`
- Found pages: `[39, 33, 19, 57, 15, 17]`
- Source hit: `True`
- Term coverage: `0.20`
- Missing terms: `["brown 'A' icon", 'any path', 'Path items', 'Path Chests']`

Top sources:
1. Page `39`: [Page 39] [Section: Thill Forest] C4 Pass A3 Northern Thill Forest used in combat on various B4 abilities: adjacent to anything in your square, in a square border with your square, or if it’s in a Southern Forest C5 including the exile using the ability. exile, not including the exile using the ability. foe, represented by a single miniature. miniature, incl…
2. Page `33`: [Page 33] [Section: Path Training] Guild is free, but it doesn’t remove from the Threat deck. / Sell items in your tuckbox. You can stow in your tuckbox. (see: Stash p.9) XP to increase your current level. Max LVL is can reach at that location. (At the POI below, Up to level 4.) Also note, when you Level Up to draw a special event. (see: Level Up p.6) active…
3. Page `33`: [Page 33] [Section: Save / Load p.34)] You choose which tokens are removed. Some smiths are better than others and can remove more tokens. • Vendor: You may sell an item for its Kae value (listed on the back of the item). You sell damaged items (with Wear tokens on and items with spent markers (e.g. an empty Potion). Put sold items back in the box. • Armorer…

### [FAIL] 流放者可以穿过其他流放者或敌人吗？移动后能停在另一个流放者的格子上吗？

- Category: `exception`
- Expected pages: `[57]`
- Found pages: `[37, 43, 39, 53, 71]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['move through other exiles', 'end their movement', 'cannot move through foes']`

Top sources:
1. Page `37`: [Page 37] [Section: Adventure Mode Movement] an Event token is in a hallway requiring that event - you cannot move past it until the Explore You can explore new maps from your current map, as your current map is cleared. • Cleared Maps: Acleared map contains no (Event or Chest) or foes. As an action, you can explore an adjacent map other players can choose t…
2. Page `43`: [Page 43] [Section: Bonus Movement] the ability, Ability is an all-encompassing term that means any type of action, skill, item, foe attack or use the map can be categorized by type, and have interacting with the map. Regardless of the ability, each other. There are four Ability Types: Amovement ability (such as Basic Move) grants to a creature, allowing it…
3. Page `39`: [Page 39] [Section: Closing a Location] Floors FOE-4 location MED-0 Locations sometimes contain multiple floors. or more maps connected to the rest of the Stairs NPC-0 Stairs are pointers to maps, so you use the Explore with them. When you explore stairs, place the new space unconnected to the rest of the location. • Exiles must always be on the same floor o…

### [FAIL] 被击倒（KO'd）的流亡者还能继续执行回合吗？他们能使用技能或物品吗？

- Category: `turn_structure`
- Expected pages: `[59]`
- Found pages: `[39, 59, 65, 51]`
- Source hit: `True`
- Term coverage: `0.50`
- Missing terms: `["KO'd exiles", 'use skills or items']`

Top sources:
1. Page `39`: [Page 39] [Section: BIG-4] Foe Turn (draw one Threat card, possibly 2. Exile Turn (one exile takes actions) For the first round, the player who triggered combat take a turn for the foes, followed by taking their player takes the ‘Explore’ action revealing a map triggered combat and after the Foe Turn, they will If combat has not ended, play passes to the pla…
2. Page `59`: [Page 59] [Section: • Weak Points] the When an exile has 0 HP while in combat, they KO’d. Place their miniature on its side to show KO’d status. • KO’d exiles still take a turn until the end of combat (there will still be a Foe Turn before turn). • KO’d exiles cannot take actions, use skills or items and cannot use or attacks granted to • KO’d exiles cannot…
3. Page `39`: [Page 39] [Section: Start of Combat] All exiles place their miniatures on the MED-17 Mode token, and then proceed to close the location. Nimbus Peninsula Closing a Location Put all remaining components for the location and associated cards back into the appropriate careful to correctly orient them based on if they The Bends Unlike the more free-form turn str…

### [PASS] 当敌人的护甲点（Armored Points）受到伤害时，应该如何结算？

- Category: `exception`
- Expected pages: `[59]`
- Found pages: `[63, 59, 61]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `63`: …Aimed damage cannot target wounded points. Piercing Damage Ablue diamond around a point of damage indicates it is Piercing damage. When applying piercing damage to Armored points, remove the Armor cube, then immediately place a Wound token. (a) first point hits top-left, second point a travels off the card.
2. Page `59`: …(see: Defeat p.33) The Hit Grid shows the current health of the foe. miniature has a matching Grid card. Hit Grids 1 • Hit Points 2 • Armored Points 3 • Weak Points 4 • Criticals:
3. Page `63`: [Page 63] [Section: FOE-0] (a) is invalid, no unwounded points. (b) FOE-0 would hit the Armored point. (c) passes through the wounded point and hits the Pra ctice Dummy Mob a Weak point on the left. (d) and (e) would hit the bottom right or left points. b e With this aimed first point of c damage, any of the remaining unwounded points (a-f) may be targeted.…


## The Castles of Burgundy

- Run time: 2026-06-03 12:22:18
- Pass: 3/9 (33%)
- Source hit: 44%
- Term coverage avg: 44%

### [FAIL] 修道院板块15在游戏结束时如何计分？未出售的货物算在种类里吗？

- Category: `end_game`
- Expected pages: `[10]`
- Found pages: `[13, 8, 12, 14, 16]`
- Source hit: `False`
- Term coverage: `0.33`
- Missing terms: `['different type of goods', 'Unsold goods']`

Top sources:
1. Page `13`: [Page 13] [Section: FINAL SCORING] bridge and you place a ship, and there is a stack of playing pieces, place your piece on top. FINAL SCORING Add up the victory points of both team members. The team with more victory points wins the game. If there is a tie, the team with more empty spaces in their duchy wins the game. (Special thanks to Matthias Nagy of “Fr…
2. Page `8`: [Page 8] [Section: Carpenter’s Workshop] • Whenever a player places the final tile of a colored area of any size, that area is considered complete and that player scores twice: 1. Depending on its size (1 to 8 spaces), the completed area gains 1-36 victory points, and the player immediately moves forward that many spaces on the victory point track. 2. In add…
3. Page `8`: [Page 8] [Section: Sell Goods] 8 An area that has been completed scores twice: 1.) Depending on its size (1-8 spaces): 1-36 victory points 2.) Depending on current phase (A-E): 10-2 victory points Who covers all spaces of a color in their duchy first gets the large bonus tile: +5/6/7 v.p. The second player gets the small bonus tile: +2/3/4 v.p. Sell Goods Di…

### [FAIL] 游戏结束时如果胜利点数平局，如何决定胜负？

- Category: `end_game`
- Expected pages: `[9]`
- Found pages: `[14, 12, 8, 7, 3]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['tie', 'fewest unused hex spaces', 'farthest behind on the bridge']`

Top sources:
1. Page `14`: [Page 14] [Section: PLAYING THE GAME] - You can only expand to other regions via the rivers. - Whenever you place a ship, take all goods from a depot of your choice, then immediately remove all other goods from all other depots from the game. In addition, you now (and only now!) have the option to exchange any 5 of your goods for a single hex tile from the c…
2. Page `12`: [Page 12] [Section: The White Castles] New duchies (nos. 11a - 11f) If you want to play with these duchies, every player receives a no. 11 duchy. They offer the following special features: When a player manages to connect two border posts in their duchy with hex tiles, they score victory points according to the current phase (i.e. 10, 8, 6, 4, or 2). Additio…
3. Page `8`: [Page 8] [Section: Carpenter’s Workshop] • Whenever a player places the final tile of a colored area of any size, that area is considered complete and that player scores twice: 1. Depending on its size (1 to 8 spaces), the completed area gains 1-36 victory points, and the player immediately moves forward that many spaces on the victory point track. 2. In add…

### [FAIL] 在单人模式中，当我完成一种颜色时，我还能获得胜利点数奖励吗？如果不能，我该怎么做？

- Category: `exception`
- Expected pages: `[14]`
- Found pages: `[8, 11, 14, 12, 6]`
- Source hit: `True`
- Term coverage: `0.33`
- Missing terms: `['complete a color', 'victory point bonus']`

Top sources:
1. Page `8`: [Page 8] [Section: Carpenter’s Workshop] • Whenever a player places the final tile of a colored area of any size, that area is considered complete and that player scores twice: 1. Depending on its size (1 to 8 spaces), the completed area gains 1-36 victory points, and the player immediately moves forward that many spaces on the victory point track. 2. In add…
2. Page `8`: [Page 8] [Section: Action "Sell Goods"] • The first player who manages to completely cover all spaces of one color in their duchy (for example by placing their third mine or sixth monastery) gets to take and immediately score the corresponding large bonus tile from the game board (5 victory points in the 2-player game, 6 in the 3-player game, or 7 in the 4-p…
3. Page `8`: [Page 8] [Section: Sell Goods] 8 An area that has been completed scores twice: 1.) Depending on its size (1-8 spaces): 1-36 victory points 2.) Depending on current phase (A-E): 10-2 victory points Who covers all spaces of a color in their duchy first gets the large bonus tile: +5/6/7 v.p. The second player gets the small bonus tile: +2/3/4 v.p. Sell Goods Di…

### [FAIL] 出售货物时，我可以只卖出同色货物的一部分，保留剩下的吗？

- Category: `exception`
- Expected pages: `[8]`
- Found pages: `[15, 12, 13, 16, 14, 11]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['sell the complete stack', 'must always sell', 'Action Sell Goods']`

Top sources:
1. Page `15`: [Page 15] [Section: PLAYING THE GAME] 6) After taking the shield, at any point in the game, choose one player. Any monastery tiles in that player’s duchy count as if they were in your own duchy. When that player places a new monastery tile, you also gain those benefits. You also gain points from any monastery scoring tiles that player may have if you have th…
2. Page `12`: …An inn can be placed on any empty hex space on your duchy (according to the Example: When you place an inn in regular rules). However, you may only place up to one inn per color area! a size 4 area, it is increased to a size 5 area and will score 15 instead of The inn itself has no effect, its only function is to complete an area. 1…
3. Page `13`: [Page 13] [Section: FINAL SCORING] bridge and you place a ship, and there is a stack of playing pieces, place your piece on top. FINAL SCORING Add up the victory points of both team members. The team with more victory points wins the game. If there is a tie, the team with more empty spaces in their duchy wins the game. (Special thanks to Matthias Nagy of “Fr…

### [FAIL] 拥有修道院板块7时，放置畜牧板块获得的额外1分是只给新放置的板块，还是同牧场上所有计分的畜牧板块都有？

- Category: `scoring`
- Expected pages: `[10]`
- Found pages: `[13, 8, 15, 16, 14, 11]`
- Source hit: `False`
- Term coverage: `0.33`
- Missing terms: `['livestock tile', 'scores at that time']`

Top sources:
1. Page `13`: [Page 13] [Section: FINAL SCORING] bridge and you place a ship, and there is a stack of playing pieces, place your piece on top. FINAL SCORING Add up the victory points of both team members. The team with more victory points wins the game. If there is a tie, the team with more empty spaces in their duchy wins the game. (Special thanks to Matthias Nagy of “Fr…
2. Page `8`: [Page 8] [Section: Sell Goods] 8 An area that has been completed scores twice: 1.) Depending on its size (1-8 spaces): 1-36 victory points 2.) Depending on current phase (A-E): 10-2 victory points Who covers all spaces of a color in their duchy first gets the large bonus tile: +5/6/7 v.p. The second player gets the small bonus tile: +2/3/4 v.p. Sell Goods Di…
3. Page `15`: [Page 15] [Section: PLAYING THE GAME] 6) After taking the shield, at any point in the game, choose one player. Any monastery tiles in that player’s duchy count as if they were in your own duchy. When that player places a new monastery tile, you also gain those benefits. You also gain points from any monastery scoring tiles that player may have if you have th…

### [FAIL] 游戏结束计分时，工人怎么换算胜利点？

- Category: `scoring`
- Expected pages: `[9]`
- Found pages: `[13, 8, 12, 14, 1]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['every two worker chips', '1 victory point']`

Top sources:
1. Page `13`: [Page 13] [Section: FINAL SCORING] bridge and you place a ship, and there is a stack of playing pieces, place your piece on top. FINAL SCORING Add up the victory points of both team members. The team with more victory points wins the game. If there is a tie, the team with more empty spaces in their duchy wins the game. (Special thanks to Matthias Nagy of “Fr…
2. Page `8`: [Page 8] [Section: Carpenter’s Workshop] • Whenever a player places the final tile of a colored area of any size, that area is considered complete and that player scores twice: 1. Depending on its size (1 to 8 spaces), the completed area gains 1-36 victory points, and the player immediately moves forward that many spaces on the victory point track. 2. In add…
3. Page `8`: [Page 8] [Section: Sell Goods] 8 An area that has been completed scores twice: 1.) Depending on its size (1-8 spaces): 1-36 victory points 2.) Depending on current phase (A-E): 10-2 victory points Who covers all spaces of a color in their duchy first gets the large bonus tile: +5/6/7 v.p. The second player gets the small bonus tile: +2/3/4 v.p. Sell Goods Di…

### [PASS] 在单人游戏中，修道院板块的胜利点数是在什么时候加上的？

- Category: `timing`
- Expected pages: `[14]`
- Found pages: `[14, 12, 16, 9, 8]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `14`: [Page 14] [Section: PLAYING THE GAME] For example, a "black mine" won’t generate silver at the end of a phase. Placing a "black ship" doesn’t gain you goods tiles or allow you to pay 5 goods to take a black hex tile. - Victory points from a monastery tile are added immediately after placing it (instead of at the end of the game). (When you place monastery ti…
2. Page `14`: [Page 14] [Section: PLAYING THE GAME] - You can only expand to other regions via the rivers. - Whenever you place a ship, take all goods from a depot of your choice, then immediately remove all other goods from all other depots from the game. In addition, you now (and only now!) have the option to exchange any 5 of your goods for a single hex tile from the c…
3. Page `12`: [Page 12] [Section: The Inns] You are allowed to use workers to change the rolled number. (To avoid confusion, don’t change the actual white die result.) The Inns Each phase, place one inn next to the central black depot. Inns are not removed like other hex tiles from the game board each phase. If there is already one or more inn next to the central black de…

### [PASS] 在回合中，我可以在什么时候花费银币从中央黑色仓库购买板块？

- Category: `timing`
- Expected pages: `[8]`
- Found pages: `[4, 8, 16, 2, 3, 9]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `4`: [Page 4] [Section: A PLAYER’S TURN] player’s turn, it’s the turn of the next player in turn order according to the playing pieces on the bridge (closer to the city center, and top to bottom if there is a stack). When all players have finished their turns, the next round begins, and so on. Since you start each phase with 5 goods tiles on the round spaces and…
2. Page `4`: [Page 4] [Section: THE FIVE GAME ROUNDS] THE FIVE GAME ROUNDS After setting up the new phase, you play 5 rounds. Each round plays the same: First, each player rolls their two dice. The starting player also rolls the white die. All dice must be visible for all players. Note: Rolling all dice simultaneously allows players to plan their turn. The starting playe…
3. Page `8`: [Page 8] [Section: Action "Sell Goods"] players (2-4)). Note: When taking this action, you must always sell the complete stack of tiles of that type, even if you would rather keep some in reserve. Action "Take 2 worker chips" Finally, any player may choose to use any die result to take two workers from the supply. The die result is irrelevant. The central "b…

### [PASS] 在单人游戏中，修道院板块的胜利点数是在游戏结束时才计算吗？

- Category: `timing`
- Expected pages: `[14]`
- Found pages: `[14, 1, 8, 9, 16]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `14`: [Page 14] [Section: PLAYING THE GAME] - You can only expand to other regions via the rivers. - Whenever you place a ship, take all goods from a depot of your choice, then immediately remove all other goods from all other depots from the game. In addition, you now (and only now!) have the option to exchange any 5 of your goods for a single hex tile from the c…
2. Page `1`: [Page 1] [Section: "The Trade Routes"] classic and The IntroductIon t is the 15th Century in duke it is your goal to lead expansion and trade. Roll your dice to reveal your victory. Whether trading or paths lead to prosperity and There are many ways to gain your strategy wisely! Thanks to a lot of variation and remains no two games play out alike. The winner…
3. Page `14`: [Page 14] [Section: END OF THE GAME] Note: You choose the order in which you take any (partial) game actions. END OF THE GAME You win the game if you managed to fill all 37 hex spaces of your duchy within 25 rounds. * If you find it too difficult to win, start the game with the target victory point marker on less than 50: 49, 48 … 45 (much easier!). If the g…


## Witcher: The old world

- Run time: 2026-06-03 12:25:06
- Pass: 2/8 (25%)
- Source hit: 62%
- Term coverage avg: 34%

### [FAIL] 当需要将一张0费行动卡加入弃牌堆，但行动卡展示区没有0费卡牌时该怎么办？

- Category: `exception`
- Expected pages: `[27]`
- Found pages: `[18, 19, 35, 16, 12, 20, 24]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['0-cost Action Card', 'Action Card Display', 'common Action Deck']`

Top sources:
1. Page `18`: …You may choose and discard any number of cards from your hand (you may have a maximum of 3 cards at the end of this step). 2. Draw Cards from your Action Deck until you have 3 Cards in your hand. • When you need to draw an Action Card but your Action Deck is empty, immediately shuffle all discarded Action Cards to create a ne…
2. Page `19`: [Page 19] [Section: Hand-Limit] Hand-Limit Your Hand-Limit is 7 cards: if you have 7 cards in your hand, and you are supposed to draw any number of additional cards, stop drawing additional cards; the effect is lost. Depending on the card’s position (in the row of cards on the Board), its cost may be modified: • If the card is on the right-most slot, you may…
3. Page `35`: [Page 35] [Section: LOCATION ACTIONS] resented by a Player your Alchemy level, If the Player is the from the top of the if the locals have won, All other rules are the Defense level, raise (see page 14). level 5). In that Location, the Active Player can from their hand, and Potion Deck. Potions available on the Game Player’s Board. If you The printed cost of…

### [FAIL] 如果我在第一阶段与另一名猎魔人玩了骰子扑克，还能在第二阶段与该猎魔人战斗吗？

- Category: `exception`
- Expected pages: `[13]`
- Found pages: `[35, 25, 20, 21, 15]`
- Source hit: `False`
- Term coverage: `0.33`
- Missing terms: `['play Dice Poker', 'fight with that Witcher']`

Top sources:
1. Page `35`: [Page 35] [Section: Once per Fight: When] Speed School School of the Cat – Once per Fight Turn, you may perform ity to draw cards possibly return some deck in any order). School of the Wolf Once per Fight: When of 3 (or more) cards, your Swordsmanship ditional Damage (and, draw additional cards). Traveling and Taking Actions on page 12). Following are the de…
2. Page `25`: [Page 25] [Section: Monster’s Attack Effects] MONSTER’S FIGHT TURN In the Monster’s Fight Turn, other Players will take turns in deciding on the Type of the Attack it will take. In its first Fight Turn, the Player controlling the Monster will choose the Attack Type. That Player says out loud, whether the Monster is Charging or Biting. After that, the top car…
3. Page `20`: [Page 20] [Section: WITCHER FIGHT RULES] WITCHER FIGHT RULES • Both Witchers prepare to fight as described in the General Fight Rules. • Both Witchers in the Fight take one Turn at a time, alternating back and forth, with the Attacking Player taking the first Turn. • The Fight ends immediately when a Witcher is Knocked-Out (as detailed above in the general r…

### [FAIL] 如果我已经拥有某个猎魔人学派的战利品，再次击败该学派的猎魔人时，还能在战利品轨道上前进吗？

- Category: `exception`
- Expected pages: `[27]`
- Found pages: `[20, 5, 8, 28, 10]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['already have a Trophy', 'Trophy Track', 'skip all steps']`

Top sources:
1. Page `20`: [Page 20] [Section: WITCHER FIGHT RULES] WITCHER FIGHT RULES • Both Witchers prepare to fight as described in the General Fight Rules. • Both Witchers in the Fight take one Turn at a time, alternating back and forth, with the Attacking Player taking the first Turn. • The Fight ends immediately when a Witcher is Knocked-Out (as detailed above in the general r…
2. Page `20`: [Page 20] [Section: WITCHER FIGHT RULES] When you are Knocked-Out by the Monster, you may still get a reward for Driving the Monster Away (explained on page 26). […] To see one of them fighting a monster is a feast for the eyes, but to see two witchers dueling is a spectacle! The one Ifound most spectacular happened in Vengerberg. One of the witchers was a W…
3. Page `5`: [Page 5] [Section: Witcher Poker Dice 35 Gold Tokens] 2 sets of Witcher Poker Dice 35 Gold Tokens arachas d i s Y o u ’ v e m a n a g e d t o t h e n t a n g l e y o u r s e l f f r o m m i n e s t i c k y w e b a t t h e l a s t r e u t e, a n d y o u r s u p e r h u m a n a w fl e x e s a l l o w e d y o u t o r o l l i n a y a n d c u t a t t h e c h a r…

### [FAIL] 当怪物被“驱赶”时，生成的新怪物等级与被击败时有什么不同？

- Category: `exception`
- Expected pages: `[26]`
- Found pages: `[33, 26, 15, 25, 16]`
- Source hit: `True`
- Term coverage: `0.33`
- Missing terms: `['Spawn a Monster', 'same level']`

Top sources:
1. Page `33`: [Page 33] [Section: Drive a Monster Away] After that, you compare your result to the Solo-Help Card. Gain Gold based on your result (see next page). Exploration Cards Any effect that asks another Player to read something, must be read by yourself. When reading, cover the card (that you are reading) with another, so that you do not see the results until you m…
2. Page `26`: [Page 26] [Section: Defeating the Monster] Draw a random Monster Token which is 1 level higher than the just Defeated Monster. Example: If a Level II Monster was Defeated, you draw a random Level III Monster token. • If Level III Monster is Defeated: draw another Level III Monster instead. • If you run out of Monster Tokens of a certain level, make a new pil…
3. Page `26`: [Page 26] [Section: Driving the Monster Away] Place the Monster Token (that was drawn during step 1) near the Location on the Game Board, that corresponds to the Location Token drawn in step 3. 5. Place the matching Monster Card in the Monster section of the Game Board. /5-Player Gameplay Changes The Additional Monster Token Stack If there is a Level I Monst…

### [FAIL] 如果我在同一回合内移出再移回某个地点，能执行两次该地点的地点行动吗？

- Category: `exception`
- Expected pages: `[13]`
- Found pages: `[9, 35, 30, 12, 36, 13]`
- Source hit: `True`
- Term coverage: `0.33`
- Missing terms: `['performed only once', 'move out']`

Top sources:
1. Page `9`: [Page 9] [Section: Action Cards] • Game Basics (page 9), • Player’s Turn Explained (page 12), • Fights (page 20), • Location Actions (page 35). We also recommend that you use this order when teaching the game – just focus on the main rules to help new Players grasp the game flow. Golden Rule Card text supersedes the Rulebook: • If any text on a card contradi…
2. Page `35`: [Page 35] [Section: LOCATION ACTIONS] At three Locations with this symbol, draw 1 Potion from the top of the are kept face-up near / or below exceed the limit of 4 Potions, tion(s) down to 4. During your first Fight Once your Speed Abil- Magic from your deck (and top of to the top of the 0-2 If this your – Swordsmanship add to you make a Combo you may perfor…
3. Page `30`: [Page 30] [Section: PHASE I – Movement and Actions] full player turn Example for a 2-Player game PHASE I – Movement and Actions The Player is a Witcher from the School of the Bear and their level is 2. Their Combat level is 3, Defense – 2, Alchemy – 2, and Specialty – 3. They have 4 Gold, Blizzard Potion, and a Trail Token for a Monster occupying a Mountain…

### [FAIL] 如果我在战斗中下注的猎魔人输了，我的赌注金币去哪里？如果下注的猎魔人赢了呢？

- Category: `scoring`
- Expected pages: `[28]`
- Found pages: `[35, 25, 20, 21, 28]`
- Source hit: `True`
- Term coverage: `0.00`
- Missing terms: `['Wager on the Witcher who lost', 'Common Pool', 'Wager on the Witcher who won', 'gain the same amount of Gold']`

Top sources:
1. Page `35`: [Page 35] [Section: Once per Fight: When] Speed School School of the Cat – Once per Fight Turn, you may perform ity to draw cards possibly return some deck in any order). School of the Wolf Once per Fight: When of 3 (or more) cards, your Swordsmanship ditional Damage (and, draw additional cards). Traveling and Taking Actions on page 12). Following are the de…
2. Page `25`: [Page 25] [Section: Monster’s Attack Effects] MONSTER’S FIGHT TURN In the Monster’s Fight Turn, other Players will take turns in deciding on the Type of the Attack it will take. In its first Fight Turn, the Player controlling the Monster will choose the Attack Type. That Player says out loud, whether the Monster is Charging or Biting. After that, the top car…
3. Page `20`: [Page 20] [Section: WITCHER FIGHT RULES] WITCHER FIGHT RULES • Both Witchers prepare to fight as described in the General Fight Rules. • Both Witchers in the Fight take one Turn at a time, alternating back and forth, with the Attacking Player taking the first Turn. • The Fight ends immediately when a Witcher is Knocked-Out (as detailed above in the general r…

### [PASS] 玩家遭遇“完全失败”后，当前回合的第三阶段抽卡数量有什么限制？

- Category: `timing`
- Expected pages: `[26]`
- Found pages: `[21, 32, 27, 28, 26, 20]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `21`: [Page 21] [Section: Life Points first Fight Turn] Any Player may always count the number of cards in the Monster Life Pool, without looking at them or changing their order. If the Active Player has a Monster Trail Token for that Monster, they take the first Turn during this Fight; otherwise, the Monster takes the first Turn. The Witcher and the Monster will…
2. Page `32`: [Page 32] [Section: Now, the Active Player] 1 sums The Active Player takes 5 Damage. First level to 0. Since they have 0 Shields left, 2 cards from the top of their deck. 2 × 2 prperceicsies eb lcouwt Now, it’s Player’s Turn again. Their Shield 1 the School of the Bear Specialty: level by 1 and 3 draw 2 cards from the + 2 prperceicsies eb clouwt 3 2 The Play…
3. Page `27`: [Page 27] [Section: Complete Defeat] The next time any Witcher attempts to fight that Monster, it will begin with a full Life Pool again. It rested-up and healed since last time. Regardless of the Fight outcome, perform the following steps: 1. Shuffle all the Monster Fight Cards together to form a new deck. 2. Shuffle the Action Cards in your deck, discard p…

### [PASS] 战斗结束后，非主动玩家如果输了，抽几张牌？主动玩家如果输了，在第三阶段抽几张牌？

- Category: `turn_structure`
- Expected pages: `[28]`
- Found pages: `[21, 18, 19, 24, 25, 20, 28]`
- Source hit: `True`
- Term coverage: `0.75`
- Missing terms: `['draw 2 cards instead of 3']`

Top sources:
1. Page `21`: [Page 21] [Section: Life Points first Fight Turn] Life Points first Fight Turn pick the Attack Type that makes the Player discard Monster’s more cards from their Special Ability deck or hand. Before the Fight, the Player controlling the Monster creates Monster’s Life Pool. That Player draws a number of Monster Fight cards from the top of the Monster Fight De…
2. Page `18`: …After traveling – encountering new places, people, and dangers – it’s time to calm your mind and prepare for the road ahead; however, a Witcher still needs to practice their new fighting and magical skills too. In this Phase, Player completes following 3 steps in order: 1. You may choose and discard any number of cards from your hand (you may have a maximu…
3. Page `19`: …iscard pile); after, slide cards to the right (to fill the empty space); then, draw 1 new card and place it on the left-most (empty) slot.! Note: Gaining a new card after losing a Fight is explained on page 27.


## knight

- Run time: 2026-06-03 12:27:57
- Pass: 2/8 (25%)
- Source hit: 75%
- Term coverage avg: 33%

### [FAIL] 当我试图烧毁修道院时，我的声望会有什么变化？我会面对什么样的守卫？

- Category: `cost`
- Expected pages: `[8]`
- Found pages: `[19, 11, 7, 5, 1, 20, 6]`
- Source hit: `False`
- Term coverage: `0.00`
- Missing terms: `['attempting to burn it', 'Reputation -3', 'violet enemy token']`

Top sources:
1. Page `19`: [Page 19] [Section: Other Solo Missions] Variants You may adjust the city levels to set up the right challenge for you. You may also use a Megapolis. Other Solo Missions This is a standard solo mission. If you wish though, you may play any other mission as solo, just use similar setup modifi cations and Special rules as this mission.
2. Page `11`: [Page 11] [Section: Wounds and Healing] In addition, take any one Advanced Action card from the Advanced Action offer. • Take a token of another player from the Common Skills area (if there are any), then put both of your revealed Skills in the Common Skills area. In addition, take the Advanced Action card from the lowest position on the Advanced Action offe…
3. Page `7`: [Page 7] [Section: AAA Player’’’’’’sss Turn] If there are no tiles in the box, no more tiles can be explored. f. For sites on a newly revealed tile, check the “When revealed” section of the associated Site Description cards and follow the text. Especially: • If a monastery is revealed, draw one Advanced Action card and add it to the Unit offer (not the Advan…

### [FAIL] 如果我移动时从一个与暴怒敌人相邻的区域移到另一个与它相邻的区域，会发生什么？

- Category: `exception`
- Expected pages: `[7]`
- Found pages: `[8, 3, 7, 11]`
- Source hit: `True`
- Term coverage: `0.00`
- Missing terms: `['provoke a rampaging enemy', 'movement immediately ends', 'attacked']`

Top sources:
1. Page `8`: [Page 8] [Section: Combat with Enemies] Healing points can be bought at villages for 3 Infl uence points and at monasteries for 2 Infl uence points (see the Description card of these sites). See the “Wounds and Healing” section. c. As described on the monastery Site Description card, a player can learn a new Advanced Action there for 6 Infl uence points. The…
2. Page `3`: [Page 3] [Section: Play Area] At the start of the game, draw 5 cards from your Deed deck (according to your Hand limit depicted on your topmost Level token). • Discard pile. Here you discard played cards at the end of your turn (and sometimes also some cards during your turn). • Figure. For now, place your fi gure here. It will move to the map during your fi…
3. Page `7`: [Page 7] [Section: AAA Player’’’’’’sss Turn] circle, draw an enemy token of the corresponding color and place it face down on the City card. 6. During movement, you may move as many spaces and explore as many tiles as you can pay Move points for. a. You are allowed to alternate between exploring new tiles and moving. b. You are allowed to play additional eff…

### [FAIL] 如果我的盾牌标记位于声望轨道的X格上，我还能与当地人互动吗？

- Category: `exception`
- Expected pages: `[8]`
- Found pages: `[4, 11, 3]`
- Source hit: `False`
- Term coverage: `0.33`
- Missing terms: `['X space', 'cannot interact']`

Top sources:
1. Page `4`: [Page 4] [Section: DEED CARDS] Unit area, including Wounded ones (Wounded Units are not healed). • Shuffles all their Deed cards to create a new Deed deck. • Draws cards up to their Hand limit. This may be increased if they are on or next to a keep or city – see the description of these sites. If next to both, use only the higher effect. This may also be inc…
2. Page `4`: [Page 4] [Section: DEED CARDS] Refresh the Spell offer – Follow the same steps as for refreshing the Advanced Action offer. f. Collect Tactic cards – Collect all Tactic cards from the previous Round, then display the appropriate set of Tactic cards in the game area, face up. g. Each player: • Flips all Banner Artifacts and Skill tokens in their play area fac…
3. Page `4`: [Page 4] [Section: DEED CARDS] All cards with this card back are Deed cards. These consist of Action cards (Basic and Advanced), Spells, Artifacts and Wounds. At the start of the game, players have only Basic Action cards in their Deed deck. 2. Each turn, players will play Deed cards from their hand. To play a card, put it in your Play area and perform the s…

### [FAIL] 寒火攻击在什么情况下会被抗性减半？

- Category: `exception`
- Expected pages: `[9]`
- Found pages: `[12, 9, 23, 8]`
- Source hit: `True`
- Term coverage: `0.00`
- Missing terms: `['Cold Fire Attacks are halved', 'Ice and Fire Resistance']`

Top sources:
1. Page `12`: [Page 12] [Section: ATTACKS] If the attack is not reduced to zero, the remainder is turned into damage that must be assigned to the blocker (either their Hero or their Units). 5. Unlike assigning damage in regular combat, the attacker chooses how to assign the damage. Contrary to a regular combat, the attacker has to have as much damage as is the Armor of th…
2. Page `9`: [Page 9] [Section: ASSIGN DAMAGE PHASE] To assign damage to your Hero, put a Wound card in your hand and reduce the damage total by your Hero’s Armor value (the left number on your Hero’s Level token). • As with Units, even if the assigned damage is lower than your Armor value, your Hero must still take a Wound. b. Repeat the above process until all Damage h…
3. Page `12`: [Page 12] [Section: ATTACKS] This can be done multiple times, and the blocker takes a Wound card in their hand each time. • The blocker can get knocked out if they get too many Wounds – see Combat with enemies. c. The attacker may leave some attack points unassigned. They have to leave them unassigned if there is no target with Armor equal to or lower than r…

### [FAIL] 当我击败敌人获得声望并跨越升级线时，我是否立即升级？

- Category: `timing`
- Expected pages: `[9]`
- Found pages: `[5, 11, 9, 8, 17]`
- Source hit: `True`
- Term coverage: `0.33`
- Missing terms: `['Level up immediately', 'end of the turn']`

Top sources:
1. Page `5`: [Page 5] [Section: “GAIN” EFFECTS] If you use another card (Magic Talent) to play Time Bending, that card is set aside instead. “GAIN” EFFECTS 1. If an effect tells you to gain a mana token, take a mana token of the corresponding color and put it in your Play area. 2. If an effect tells you to gain a crystal, take a mana token of the corresponding color and…
2. Page `5`: [Page 5] [Section: “GAIN” EFFECTS] If you do not understand an effect or the interaction of two or more effects in combination, check the game website for FAQs. 5 “COMPOSITE” EFFECTS 1. Some cards (Concentration, Magic Talent, etc.) allow you to play the effect of another card or token as part of their effect (some even multiple times – Maximal effect). a. T…
3. Page `11`: [Page 11] [Section: CITY ASSAULTS] Use the benefits of your space: a. If you end your turn on a magical glade, you may throw away one Wound card from your hand or discard pile. Units cannot be Healed this way. b. If you end your turn on a crystal mine, you gain a crystal of the mine’s color to your Inventory (unless you have 3 crystals of that color already…

### [FAIL] 如果我是本轮第一个行动的玩家，我能在自己的第一个回合之前使用"在其他玩家回合"的效果吗？

- Category: `timing`
- Expected pages: `[6]`
- Found pages: `[23, 4, 6, 17]`
- Source hit: `True`
- Term coverage: `0.00`
- Missing terms: `['before your first turn', "on another player's turn", 'first player to play this Round']`

Top sources:
1. Page `23`: …– If your hand is also empty, you have to do this. Regular turn: Optional movement (and/or map revealing), then optional (sometimes mandatory) action: – Combat with enemies (assault to a fortified site, provoking or challenging rampaging enemies, entering an adventure site). – Interaction with locals (recruiting, healing…
2. Page `4`: [Page 4] [Section: DEED CARDS] Unit area, including Wounded ones (Wounded Units are not healed). • Shuffles all their Deed cards to create a new Deed deck. • Draws cards up to their Hand limit. This may be increased if they are on or next to a keep or city – see the description of these sites. If next to both, use only the higher effect. This may also be inc…
3. Page `4`: …c. Create a new Unit offer. • Take all Unit cards currently in the offer and put them on the bottom of their corresponding decks. • I f there are some Advanced Action cards in the Unit offer, put them to the bottom of the Advanced Action deck. • Deal new Unit cards into the Unit offer equal to the number of actual players plus 2. • I f no…

### [PASS] 进入城市的移动点数消耗会受昼夜地形变化的影响吗？

- Category: `cost`
- Expected pages: `[7]`
- Found pages: `[21, 7, 23, 11, 3, 4]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `21`: …• All conquered tombs and dungeons (including the secret ones) are connected. – When on a conquered dungeon or tomb space during movement, you may move to any other conquered dungeon or tomb space.
2. Page `7`: [Page 7] [Section: AAA Player’’’’’’sss Turn] Some effects modify the rules of movement. These apply to all movement done after the effect is played, until the end of turn. a. Some effects reduce the Move cost of certain terrains. If a player plays more than one of this type of effect, they can apply them in any order. If the Move cost of a terrain is reduced…
3. Page `7`: [Page 7] [Section: AAA Player’’’’’’sss Turn] P Pllaayyeerrss can also play any number of special and healing effects during movement. 3. Total the Move points provided by all your cards and effects. You may then move your fi gure, space by space, spending Move points according to the type of terrain you are moving into (as indicated by the Day/Night board).…

### [PASS] 行动牌堆为空时，什么情况下必须宣告回合结束？什么情况下可以选择不宣告？

- Category: `end_game`
- Expected pages: `[6]`
- Found pages: `[23, 4, 6]`
- Source hit: `True`
- Term coverage: `1.00`
- Missing terms: `[]`

Top sources:
1. Page `23`: …– If your hand is also empty, you have to do this. Regular turn: Optional movement (and/or map revealing), then optional (sometimes mandatory) action: – Combat with enemies (assault to a fortified site, provoking or challenging rampaging enemies, entering an adventure site). – Interaction with locals (recruiting, healing…
2. Page `4`: [Page 4] [Section: DEED CARDS] Unit area, including Wounded ones (Wounded Units are not healed). • Shuffles all their Deed cards to create a new Deed deck. • Draws cards up to their Hand limit. This may be increased if they are on or next to a keep or city – see the description of these sites. If next to both, use only the higher effect. This may also be inc…
3. Page `6`: [Page 6] [Section: AAA Player’’’’’’sss Turn] You may do only one action each turn (mandatory or voluntary). If you want to move and/or reveal new tiles, you must do it before taking an action. You cannot move or reveal map tiles after an action. e. Unspent Move points and Infl uence points from previous phases of your turn are lost at the moment you start yo…
