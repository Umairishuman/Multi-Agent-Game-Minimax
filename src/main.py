from Game import Game
def main():
    
    game = Game("input/board.txt")
    # game.play()        # Console mode
    game.run_gui()      # GUI mode

if __name__ == "__main__":
    main()