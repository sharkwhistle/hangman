"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email =ndb.StringProperty()
    wins = ndb.IntegerProperty(default=0)
    total_games = ndb.IntegerProperty(default=0)

    """Win percentage and win/loss calculation"""
    @property
    def win_percentage(self):
        if self.total_games > 0:
            return float(self.wins)/float(self.total_games)
        else:
            return 0

    def to_form(self):
        return UserForm(name=self.name,
                        email=self.email,
                        wins=self.wins,
                        total_games=self.total_games,
                        win_percentage=self.win_percentage)

    def add_win(self):
        self.total_games += 1
        self.wins += 1
        self.put()

    def add_loss(self):
        self.total_games += 1
        self.put()

class Game(ndb.Model):
    """Game object"""
    target = ndb.StringProperty(required=True)
    letters_guessed = ndb.StringProperty(required=True, default='')
    correct_letters = ndb.StringProperty(required=True, default='')
    guessed_word = ndb.StringProperty(required=True)
    attempts_allowed = ndb.IntegerProperty(required=True, default=13)
    attempts_remaining = ndb.IntegerProperty(required=True, default=13)
    game_over = ndb.BooleanProperty(required=True, default=False)
    history = ndb.StringProperty(repeated=True)
    user = ndb.KeyProperty(required=True, kind='User')

    @classmethod
    def new_game(cls, user):
        """Creates and returns a new game"""
        words = ["cat", "dog", "bat", "dosa", "dinosaur", "biscuits"]
        target_word = random.choice(words)
        blank_string = "_" * len(target_word)
        game = Game(user=user,
                    target=target_word,
                    guessed_word=blank_string)
        game.put()
        return game

    def to_form(self, message):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.guessed_word = self.guessed_word
        form.letters_guessed = self.letters_guessed
        form.attempts_allowed = self.attempts_allowed
        form.attempts_remaining = self.attempts_remaining
        form.game_over = self.game_over
        form.history = self.history
        form.message = message
        return form

    def end_game(self, won=False):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        self.put()

        #Add win or loss to game
        if won == True:
            self.user.get().add_win()
        else:
            self.user.get().add_loss()

        # Add the game to the score 'board'
        score = Score(user=self.user, date=date.today(), won=won,
                      guesses=self.attempts_allowed - self.attempts_remaining)
        score.put()


class Score(ndb.Model):
    """Score object"""
    user = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    guesses = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(user_name=self.user.get().name, won=self.won,
                         date=str(self.date), guesses=self.guesses)


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_allowed = messages.IntegerField(2, required=True)
    attempts_remaining = messages.IntegerField(3, required=True)
    game_over = messages.BooleanField(4, required=True)
    message = messages.StringField(5, required=True)
    user_name = messages.StringField(6, required=True)
    guessed_word = messages.StringField(7, required=True)
    letters_guessed = messages.StringField(8, required=True)
    history = messages.StringField(9, repeated=True)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    guesses = messages.IntegerField(4, required=True)
    

class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)

    
class UserRankingForm(messages.Message):
    """Return Form of User score rankings"""
    user_name = messages.StringField(1, required=True)
    avg_score = messages.FloatFiled(2, required=True)
    
    
class UserRankingForms(messages.Message):
    """Return multiple UserRankingForms"""
    items = messages.Message(UserRankingForm, 1, repeated=True)
    
    
class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)

    
class UserForm(messages.Message):
    """Form representation of User information"""
    name = messages.StringField(1, required=True)
    email = messages.StringField(2, required=True)
    wins = messages.IntegerField(3, required=True)
    total_games = messages.IntegerField(4, required=True)
    win_percentage = messages.FloatField(5, required=True)

    
class UserForms(messages.Message):
    """Return multiple UserForms"""
    items = messages.MessageField(UserForm, 1, repeated=True)
