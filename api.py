# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""


import logging
import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import User, Game, Score
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm,\
    ScoreForms, UserForm, UserForms, UserRankingForm, UserRankingForms
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
        urlsafe_game_key=messages.StringField(1),)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))
HIGH_SCORES = endpoints.ResourceContainer(number_of_results=messages.IntegerField(1))

USER_RANKINGS = endpoints.ResourceContainer()

MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'

@endpoints.api(name='hangman', version='v1')
class HangmanApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                    'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        return StringMessage(message='User {} created!'.format(
                request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        game = Game.new_game(user.key)

        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing Hangman!')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            raise endpoints.ConflictException('Game already over!')

        if request.guess.isalpha() == False:
            raise endpoints.ConflictException('Guess must be a leter!')

        if len(request.guess) > 1:
            raise endpoints.ConflictException('One at a time!')

        if request.guess in game.letters_guessed:
            raise endpoints.ConflictException('Letter already guessed!')

        if request.guess in game.target:
            msg = "That letter is in the target word!"
            game.letters_guessed += request.guess
            game.correct_letters += request.guess
            game.history.append(request.guess)
        else:
            msg = "That letter is not in the target word!"
            game.letters_guessed += request.guess
            game.attempts_remaining -= 1
            game.history.append(request.guess)

        for i in range(len(game.target)):
            if game.target[i] in game.letters_guessed:
                game.guessed_word = game.guessed_word[:i] + game.target[i] \
                + game.guessed_word[i + 1:]
        if game.guessed_word == game.target:
            game.end_game(True)
            return game.to_form("You guessed the correct word!")

        if game.attempts_remaining < 1:
            msg = "Game over!"
            game.end_game(False)
        else:
            game.put()
        return game.to_form(msg)


    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self,request):
        """Cancel current active game"""
        game = get_by_urlsafe(request.urlsafe_game_key,Game)
        if game and not game.game_over:
            game.key.delete()
            return StringMessage(message='Game canceled!')
        elif game and game.game_over:
            raise endpoints.ConflictException('Game already over!')
        else:
            raise endpoints.NotFoundException('No active game found!')


    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        return ScoreForms(items=[score.to_form() for score in Score.query()])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])
    
    @endpoints.method(request_message=HIGH_SCORES,
                      response_message=ScoreForms,
                      path='highscores',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """Returns Leaderboard of high scores"""
        if request.number_of_results is not None:
            scores = Score.query().order(Score.score).fetch(request.number_of_results)
        else:
            scores = Score.query().order(Score.score)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoint.method(request_message=USER_REQUEST,
                     response_method=UserForms,
                     path='games/{user_name}',
                     name='get_user_games',
                     http_method='GET')
    def get_user_games(self, request):
        """Returns all user games"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException('No user with that name!')
        games = Game.query(Game.user == user.key, Game.game_over == False)
        return GameForms(items=[game.to_form() for game in games])
        
    @endpoints.method(request_message=USER_RANKINGs,
                      response_message=UserRankingForms,
                      path='user/rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self,request):
        """Return all user wins and win percentages"""
        users = User.query(User.total_games > 0).fetch()
        users = sorted(users, key=lambda x: x.win_percentage, reverse=True)
        return UserRankingForms(items=[user.to_form() for user in users])

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/{urlsafe_game_key}/history',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self,request):
        """Return game history"""
        game = get_by_urlsafe(request.urlsafe_game_key,Game)
        if not game:
            raise endpoints.NotFoundException('No active game!')
        else:
            return StringMessage(message=str(game.history))

    @endpoints.method(response_message=StringMessage,
                      path='games/average_attempts',
                      name='get_average_attempts_remaining',
                      http_method='GET')
    def get_average_attempts(self, request):
        """Get the cached average moves remaining"""
        return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')

    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over == False).fetch()
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining
                                        for game in games])
            average = float(total_attempts_remaining)/count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'.format(average))


api = endpoints.api_server([HangmanApi])
