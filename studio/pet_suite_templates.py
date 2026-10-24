"""Local animation recipe definitions for the standalone editor."""
TEMPLATES={
 'Idle / Breathing':['Neutral','Inhale','Hold','Exhale'],
 'Walking':['Contact left','Down','Passing left','Contact right','Down','Passing right'],
 'Sleeping':['Lie down','Eyes close','Slow inhale','Slow exhale'],
 'Eating':['Look at food','Open mouth','Bite','Chew','Swallow','Reset'],
 'Happy / Celebrating':['Ready','Crouch','Jump','Peak','Land','Reset'],
 'Grooming':['Sit','Raise paw','Lick paw','Wipe face','Wipe face again','Lower paw','Blink','Reset'],
 'Flying / Hovering':['Wings up','Mid down','Wings down','Glide','Mid up','Wings up'],
 'Custom':['Start','Middle','End'],
}
TEMPLATES.update({'Sitting Down': ['Standing', 'Bend knees', 'Lower body', 'Seated'], 'Yawning': ['Resting', 'Open mouth', 'Wide yawn', 'Close mouth'], 'Drinking': ['Look at water', 'Lower head', 'Sip', 'Lift head'], 'Stretching': ['Rest', 'Lean forward', 'Full stretch', 'Relax'], 'Curious Head Tilt': ['Look forward', 'Tilt left', 'Hold', 'Return'], 'Hopping': ['Ready', 'Squash', 'Hop up', 'Land'], 'Being Petted': ['Neutral', 'Notice hand', 'Lean into pet', 'Content'], 'Confused': ['Neutral', 'Look left', 'Tilt head', 'Blink'], 'Excited': ['Anticipate', 'Bounce up', 'Land', 'Bounce again', 'Settle'], 'Sad / Lonely': ['Neutral', 'Lower head', 'Hold', 'Slow sigh'], 'Angry / Pouting': ['Neutral', 'Frown', 'Stomp', 'Hold'], 'Shy / Blushing': ['Notice', 'Look away', 'Blush', 'Peek back'], 'Startled': ['Rest', 'Surprise', 'Jump back', 'Recover'], 'Bored': ['Rest', 'Look away', 'Slow blink', 'Rest'], 'Affectionate': ['Notice friend', 'Lean forward', 'Nuzzle', 'Return'], 'Running': ['Contact left', 'Push off', 'Flight', 'Contact right', 'Push off', 'Flight'], 'Turning Around': ['Front', 'Quarter turn', 'Side', 'Three-quarter', 'Back'], 'Sniffing': ['Look around', 'Lean forward', 'Sniff', 'Sniff again', 'Lift head'], 'Looking Around': ['Center', 'Look left', 'Center', 'Look right'], 'Getting Picked Up': ['Standing', 'Reach', 'Rise', 'Dangle', 'Settle'], 'Waving Hello': ['Rest', 'Raise paw', 'Wave left', 'Wave right', 'Lower paw'], 'Falling Asleep': ['Awake', 'Drowsy', 'Eyes closing', 'Asleep'], 'Pooping': ['Stand', 'Squat', 'Hold', 'Finish', 'Stand']})
REQUIRED={'Walking':['Body','Legs / paws'],'Flying / Hovering':['Body','Wings'],'Eating':['Head','Mouth']}
