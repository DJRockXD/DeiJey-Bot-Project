# DeiJey-Bot-Project
LAUNCH: DeijayMain & dataHandlingServer . Other Modules are meant to organize the code, they don't need to be run.
For a more complete overview, see the Project Book combined in the repository.

My Graduation Project.
For a more complete overview, see "Project Book" in the repository.
The project is meant to aide with automization of tasks the user does. 
The bot has some base functions allowing it to remember the mouse coordinates and labeling it with a name. "dj, save mouse location as chrome" for example, will allow the program to later understand the command "dj, jump to chrome".
Additionally, this bot is fairly language-intelligent. Specific wording is not necessary for it to understand commands, as it uses a KEYWORD-based interpretation of the user's commands.
For example, if it hears the word "Save this location uuuh, as, uuhhh, as Start Button!", it hears the words "Save" together with "Location". Thus it will know that the user wants to save a location as anything following the last heard "as".

By using these small building blocks, the main functionality of the program emerges:
1. RECORDING a user's commands through a voice command, and STOPPING the recording via another command.
2. REMEMBERING and LABELING this set of recorded actions as a "PROTOCOL".
3. EXECUTING this "PROTOCOL" via voice input by the user.

!!!!
This functionality allows the user to TEACH the program a certain move-set, and to never have to repeat this set of moves again.
Want to never have to get up from your couch to skip to the next episode? Just tell Deijey "dj, Next episode!" and it'll happen in moments. After you taught it to him by telling him something along the lines of "Start recording", of course.
Want to enter your looong and complicated password but don't want to type it for 10 seconds straight? Just say aloud "dj, type in my League of Legends password"
!!!!

------------------------------------------------------------------------------------------
IMPORTANT MESSAGES!
* Must have a microphone connected to launch program.
* Must launch on an Interpreter. Didn't add stand-alone functionality to this project.
* The project is set to work in ONE computer. To change this, simply switch the IP global variable in both Server and Client to connect two computers together.
* BEFORE RUNNING, ensure the following libraries are installed:
  1. _pickle
  2. pyautogui
  3. mouse
  4. speech_recognition
  5. pyttsx3

------------------------------------------------------------------------------------------

This project uses advanced concepts such as Threading, Networking, API usage, Logging for error debugging and tracking, TCP & UDP Protocols, Object Oriented Programming & Class Overriding, and an attempt at creating a database.

I have my qualms about how I wrote it: 
the database could've been much more easily created using SQL, I could've added some packaging to make installing this easier, and the code could stand to have more comments explaining it.
Regardless, I'm proud of the time I spent learning new things for this project. It was really fun.

