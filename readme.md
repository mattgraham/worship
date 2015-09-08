## Worship Collection in ChordPro Format

Please remember to pay your CCLI license if you are playing these for your church or out in the public. These are resources available but not meant to cheat the artist out of their rewards for their hard work. 

The ChordPro file format is common format used in other software applications. The ChordPro format allows for song information to be expressed in tags with curly braces. The following are metatags supported by OnSong's implementation of the format:

- **title** or **t** is the title of the song
- **subtitle**, **st** or **su** is the artist name or any other byline information
- **album** or **a** is the name of the album where the song is located
- **artist**: The artist name or any other byline information
- **key**: The key of the song -- alphabetic, major or minor
- **capo**: The capo to set as number of frets -- numeric
- **tempo**: The beats per minute (BPM) -- numeric
- **time**: The time signature -- numeric beat over bar -- 3/4
- **duration**: The song length for autoscroll -- seconds or mm:ss
- **flow**: The arrangement of sections -- list of section labels. See Flow for details on arranging the flow of a song.
- **comment** or **c** defines a comment and appears as a musical instruction
- **guitar_comment** or **gc** defines a comment that appears as a musical instruction
- **start_of_chorus** or **soc** declares the start of a chorus section
- **end_of_chorus** or **eoc** declares the end of a chorus section
- **start_of_tab** or **sot** declares the start of tablature which OnSong renders in a monospaced font.
- **end_of_tab** or **eot** declares the end of a tablature section.
- **define** used to define custom chord diagrams. See Defining Chords for more information.
- **copyright** specifies copyright information
- **footer** specifies footer text to appear at the bottom of the page or lyrics projection.
- **book**: The name of the book to place the song into
- **number**: The number of the song -- numeric, use for hymns, years, etc
- **keywords**: The list of tags to use with topic search. See Topics for more information on browsing by topic.
- **ccli**: The CCLI number of the song
- **restrictions**: The rights management for the song Comma-delimited list of restrictions. See Restrictions for details on setting restrictions for your song.
- **textsize** defines the size of the lyrics as a numeric value in points.
- **textfont** defines the name of the font to use for lyrics. Must be supported on the platform.
- **chordsize** defines the size of the chords as a numeric value in points.
- **chordfont** defines the name of the font to use for chords. Must be supported on the platform.

**For more information on the ChordPro file format, please see ChordPro Song File Format Reference.
