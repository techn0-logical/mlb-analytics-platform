#!/usr/bin/env python3
"""This line allows this application file to be ran as a shell script"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Database.config.database import db_config
from Database.models.models import GamePrediction, Game
from sqlalchemy.orm import Session
from datetime import date, datetime
import Application.Functions as Functions

"""Here I will make my GUI which I will use to navigate all parts of the app"""

print("Welcome to MLB Games predictor\n")

while True:
    print("Choose an option:")
    print("1. Predictions")
    print("2. Update database")
    print("3. Run collector")
    print("4. Exit")
    choice = input("Enter option (1-4): ")

    if choice == "1":
        while True:
            print("\nChoose an Option:")
            print("1. Show Today's Predictions")
            print("2. Make predictions")
            print("3. Update Predictions")
            print("4. Go Back")
            print("5. Exit")
            option = input("Enter option (1-4): ")
            
            if option == "1":
                Functions.show_predictions()
                continue
            elif option == "2":
                date = input("Enter date (YYYY-MM-DD): ")
                try:
                    target_date = datetime.strptime(date, "%Y-%m-%d").date()
                    Functions.get_games(target_date)
                except ValueError:
                    print("Invalid date format. use YYYY-MM-DD")
                continue
            elif option == "3":
                print("this method needs work")
                continue
            elif option == "4":
                print("this method needs work")
                continue
            elif option == "5":
                sys.exit()
            else:
                print("\nPlease select 1-5")

        continue
    elif choice == "2":
        print("Updating database...")
        continue
    elif choice == "3":
        print("Running collector...")
        continue
    elif choice == "4":
        print("Exiting.")
        sys.exit()
    else:
        print("Please select option 1-4")
        continue