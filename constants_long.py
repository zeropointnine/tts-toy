class ConstantsLong:

    MENU_TEXT = """[title+b]End-user system prompt:

    Enter some text. That's it. 

[title+b]Special commands:

    [blue]!chat[light] or [blue]!c[light] - switch to "chat mode" 
    [blue]!direct[light] or [blue]!d[light] - switch to "direct input mode"

    voices:
        [blue]!tara, !leah, !jess, !leo, !dan, !mia, !zac, !zoe, 
        [blue]!random

    [blue]!stop[light] or [blue]!s[light] - stop audio output
    [blue]!clear[light] - clear chat history 

    [blue]!save[light] - save audio output to disk (toggle) %save

    [blue]!help[light] - this help text"""

    # ------------------------------------------------------------------------------------

    TEST_TEXT_0 = "Two years ago, a friend of mine asked me to say some MC rhymes, so I said this rhyme I'm about to say, the rhyme was deffer when it went this way."

    TEST_TEXT_1 = "This is the first sentence. This is a second sentence, which is a bit longer and might need splitting based on word count, but this part right here is also quite lengthy and might itself require a hard split even after the comma separation especially after this phrase which makes it extra-verbose. Here is a third sentence; it uses a semicolon. A fourth: with a colon. This fifth sentence is deliberately made very long to ensure that the splitting mechanism based on word count and phrase separators like commas, semicolons, or colons is triggered effectively, hopefully creating multiple chunks from this single sentence alone. Mr. Smith went to Washington D.C. for a meeting. What about questions? This should work!"

    TEST_TEXT_2 = """Oh, that's a good question <giggle>

Well, it really depends on what you mean by "strongest" and what content you're tackling, you know

    But, if we're talking about raw damage output, and considering the current meta, here's a general idea, though it's always changing

First, there's Hu Tao, she's a Pyro character, and she's known for her insane single-target damage, especially when she's played well

Then, there's Raiden Shogun, she's Electro, and she's a fantastic all-arounder, great for both single-target and AoE, and she helps with energy recharge for the team

Next, we have Ganyu, she's Cryo, and she's a ranged DPS, her charged attacks hit like a truck, especially in the right team comps

And, of course, there's Ayaka, also Cryo, she's a great option for a freeze team, and she deals a lot of damage consistently

There are others, of course, like Xiao, he's Anemo, and he's a great plunge attacker, and then there's Itto, he's Geo, and he's a powerful on-field DPS

It really depends on your playstyle, and what characters you enjoy playing, but those are some of the top contenders, I think <chuckle>"""

    TEST_TEXT_3 = "Mr. Smith went to Washington D.C. for... a meeting."

    DEV_PROMPT_SHORTCUTS = {
        "0": TEST_TEXT_0,
        "1": TEST_TEXT_1,
        "2": TEST_TEXT_2,
        "3": TEST_TEXT_3
    }
