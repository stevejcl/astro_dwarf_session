# astro_dwarf_session
 Automatic Sessions For Dwarf 2 and 3

Dwarf II,Dwarf 3 sofware for automatic imaging sessions

This program permits to start automatically imaging sessions 

The sessions are defined in a json file in a specific directory: ./Astro_Sessions/ToDo/

the json use this format samples are provided in ./Astro_Session directory : 
 
        { "command" : {
                "id_command" : {
                    "uuid" : "uuid";
                    "description": "text";
                    "date" : date; # "YYYY-MM-DD" minimun date to launch the processing, can be later if a processing is in progress
                    "time" : time; # "HH:MM:SS"
                    "process" : {wait, pending, ended}; # "wait" to be proccessed
                    "max_retries": 2, # maximun number of retries in case of errors
                    "result" : boolean; # result after processing
                    "message" : {...};  # result message
                    "nb_try": 1, # number of tries done
                    "processed_date": date; # YYYY-MM-DD HH:MM:SS date of proccessing
                }

                "calibration" : {
                    "do_action" : false; # true to do the action
                    "wait_before" : time_sec;
                    "wait_after" : time_sec;
                }
                "goto_solar" :  {
                    "do_action" : false;
                    "target" : planet_name;
                    "wait_after" : time_sec;
                }
                "goto_manual" :  {
                    "do_action" : false;
                    "target" : target_name;
                    "ra_coord" : ra_coord; # decimal value or HH:MM:SS
                    "dec_coord" : dec_coord; # decimal value or DD:MM:SS
                    "wait_afte"r : time_sec;
                }
                "setup_camera" :  {
                    "do_action" : false;
                    "exposure" : exposure_strvalue;
                    "gain" : gain_strvalue;
                    "binning" : binning_val;   # "0": 4k - "1": 2k
                    "IRCut" : IRCut_val;     # "0": IRCut - "1": IRPass for D2, "0": VIS Filter - "1": Astro Filter - "2" for DUAL BAND Filter for D3
                    "count" : nb_image;
                    "wait_after" : time_sec;
                }
            }
        }



Installation

1. Clone this repository 

2. Then Install the dwarf_python_api library with :
  
     python -m pip install -r requirements.txt
   
     python -m pip install -r requirements-local.txt --target .

   This project uses the dwarf_python_api library that must be installed locally in the root path of this project
   with using the parameter --target .

   Don't miss the dot at the end of the line

Then you can start it with => python .\astro_dwarf_scheduler.py

At the beginning, it will ask if you want to connect to the dwarf with bluetooth to start STA Mode.
It will ask the same thing after an error at the end of an action processing, but il wait only 60s in this case.

3. Prepare manually your sessions files, this will be done later with Dwarfium

4. Copy your files in the ./Astro_Sessions/ToDo/ sudirectory, they will be processed automatically

5. To stop the processing use CRL+C

6. Clear nights and good night too, the dwarf will work for you ;)
