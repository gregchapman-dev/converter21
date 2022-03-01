from fractions import Fraction
import music21 as m21
print(m21.__version__)

# test PR #1240
restVoice = m21.stream.Voice()
positionedRest = m21.note.Rest()
positionedRest.duration = m21.duration.Duration(Fraction(1, 3))
restVoice.insert(Fraction(11, 3), positionedRest)
restVoice.makeRests(inPlace=True,
                    hideRests=True)

for i, rest in enumerate(restVoice.notesAndRests):
    print(f'rest[{i}] = {rest}')
    print(f'rest[{i}].duration = {rest.duration}')
    print(f'rest[{i}] tuplets = {rest.duration.tuplets}')
    print(f'rest[{i}] components = {rest.duration.components}')

print('')


'''
# test makeAccidentals
s = m21.stream.Score()
p = m21.stream.Part()
m1 = m21.stream.Measure()
m2 = m21.stream.Measure()

s.insert(0, p)
p.insert(0, m1)
p.append(m2)

m1.append(m21.clef.TrebleClef())
m1.append(m21.key.Key('D-')) # 5 flats, B, E, A, D, and G
m1.append(m21.meter.TimeSignature('4/4'))

n1 = m21.note.Note('E-4')
n1.pitch.accidental.displayType = 'normal'
n2 = m21.note.Note('D-4')
n2.pitch.accidental.displayType = 'normal'
n3 = m21.note.Note('G4')
n3.pitch.accidental = m21.pitch.Accidental('natural')
n3.pitch.accidental.displayType = 'normal' # this one will (CWMN rules) display a natural sign
n4 = m21.note.Note('D4')
n4.pitch.accidental = m21.pitch.Accidental('natural')
n4.pitch.accidental.displayType = 'normal' # this one will (CWMN rules) display a natural sign
m1.append(n1)
m1.append(n2)
m1.append(n3)
m1.append(n4)

n5 = m21.note.Note('E-4')
n5.pitch.accidental.displayType = 'normal'
# I mark the following D-flat to be cautionary
n6 = m21.note.Note('D-4')
n6.pitch.accidental.displayType = 'always' # cautionary flat I specified, and I get (yay)
n7 = m21.note.Note('G-4')
n7.pitch.accidental.displayType = 'normal' # cautionary flat I did NOT specify, and I get (boo)
n8 = m21.note.Note('D4')
n8.pitch.accidental = m21.pitch.Accidental('natural')
n8.pitch.accidental.displayType = 'normal' # this one will (CWMN rules) display a natural sign
m2.append(n5)
m2.append(n6)
m2.append(n7)
m2.append(n8)

p.makeAccidentals() # I've tried setting all cautionary* args to False, but that didn't help

s.show('musicxml.pdf')
outputFile = s.write(fmt='musicxml', fp=None, makeNotation=False)
print('output musicxml is in', outputFile)
'''


'''
# testClef
s = m21.stream.Score()
p = m21.stream.Part()
m = m21.stream.Measure(1)
v1 = m21.stream.Voice()
v2 = m21.stream.Voice()

s.append(p)
p.append(m)

# m starts with a bass clef, v1 and v2 both start with a treble clef
m.append(m21.clef.BassClef())
m.append(m21.key.Key('g'))
m.append(m21.meter.TimeSignature('4/4'))
m.append(m21.clef.TrebleClef()) # put it in the measure instead
m.insert(0, v1)
m.insert(0, v2)

#v1.insert(0, m21.clef.TrebleClef()) # in measure now

n1v1 = m21.note.Note('B-3')
n2v1 = m21.note.Note('D4')
n3v1 = m21.note.Note('G4')
n4v1 = m21.note.Note('A3')
v1.append(n1v1)
v1.append(n2v1)
v1.append(n3v1)
v1.append(n4v1)

#v2.insert(0, m21.clef.TrebleClef()) # in measure now (but only once)

n1v2 = m21.note.Note('G3')
n1v2.duration.quarterLength = 4

v2.append(n1v2)

s.show('musicxml.pdf')
outputFile = s.write(fmt='musicxml', fp=None, makeNotation=False)
print('output musicxml is in', outputFile)
'''

'''
# test DynamicWedge horizontal offsets

# method: invisible rest in a special "timing" voice
s = m21.stream.Score()
p = m21.stream.Part()
m = m21.stream.Measure(1)
v1 = m21.stream.Voice() # where the notes are
v2 = m21.stream.Voice() # special timing voice with only invisible rests

s.append(p)
p.append(m)

m.insert(0, m21.clef.TrebleClef())
m.insert(0, m21.key.Key('G'))
m.insert(0, m21.meter.TimeSignature('3/4'))
m.insert(0, v1)
m.insert(0, v2)

v1n0 = m21.note.Note('G4')
v1n1 = m21.note.Note('A4')
v1n2 = m21.note.Note('B4')

# invisible rest every eighth note
v2r0 = m21.note.Rest()
v2r0.duration.quarterLength = 0.5
v2r0.style.hideObjectOnPrint = True
v2r1 = m21.note.Rest()
v2r1.duration.quarterLength = 0.5
v2r1.style.hideObjectOnPrint = True
v2r2 = m21.note.Rest()
v2r2.duration.quarterLength = 0.5
v2r2.style.hideObjectOnPrint = True
v2r3 = m21.note.Rest()
v2r3.duration.quarterLength = 0.5
v2r3.style.hideObjectOnPrint = True
v2r4 = m21.note.Rest()
v2r4.duration.quarterLength = 0.5
v2r4.style.hideObjectOnPrint = True
v2r5 = m21.note.Rest()
v2r5.duration.quarterLength = 0.5
v2r5.style.hideObjectOnPrint = True

v1.append((v1n0, v1n1, v1n2))
v2.append((v2r0, v2r1, v2r2, v2r3, v2r4, v2r5))
cresc = m21.dynamics.Crescendo()
cresc.addSpannedElements(v1n0, v2r2) # Crescendo should be 3 8th notes long (start of measure to end of v2r2)
dim = m21.dynamics.Diminuendo()
dim.addSpannedElements(v2r3,v1n2) # Diminuendo should start with v2r3 (offset=3 8th notes), end with v1n2 (end of measure)
s.insert(0, cresc)
s.insert(0, dim)

s.show('musicxml.pdf', makeNotation=False)
outputFile = s.write(fmt='musicxml', fp=None, makeNotation=False)
print('output musicxml is in', outputFile)
'''

'''
# method: invisible TextExpression ('') or Dynamic in the same Voice whose offset is where you want the Dynamic to start/end
# THIS DOESN'T WORK: the end/start lands at the end of the note just _after_ the TextExpression/Dynamic.
s = m21.stream.Score()
p = m21.stream.Part()
m = m21.stream.Measure(1)
v1 = m21.stream.Voice() # where the notes are (and the invisible TextExpressions/Dynamics) are

s.append(p)
p.append(m)

m.insert(0, m21.clef.TrebleClef())
m.insert(0, m21.key.Key('G'))
m.insert(0, m21.meter.TimeSignature('3/4'))
m.insert(0, v1)

v1n0 = m21.note.Note('G4')
v1n1 = m21.note.Note('A4')
v1n2 = m21.note.Note('B4')

# TextExpression at offset 3 eighth-notes in
v1InvisDir = m21.dynamics.Dynamic('p')
v1InvisDir.style.hideObjectOnPrint = True

v1.append((v1n0, v1n1, v1n2))
v1.insert(1.5, v1InvisDir) # offset == 1.5 == 3 eighth-notes
cresc = m21.dynamics.Crescendo()
cresc.addSpannedElements(v1n0, v1InvisDir) # Crescendo should be 3 8th notes long (start of measure to 3/8)
dim = m21.dynamics.Diminuendo()
dim.addSpannedElements(v1InvisDir, v1n2) # Diminuendo should start 3/8ths, end with v1n2 (end of measure)
s.insert(0, cresc)
s.insert(0, dim)

s.show('musicxml.pdf', makeNotation=False)
outputFile = s.write(fmt='musicxml', fp=None, makeNotation=False)
print('output musicxml is in', outputFile)
'''
