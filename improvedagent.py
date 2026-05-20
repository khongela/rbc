import chess.engine
import random
import math
from reconchess import *
import os
from collections import Counter
from typing import List, Optional, Tuple, Dict, Set



class ImprovedAgent(Player):
    """
    Improved version of the TroutBot with Shannon entropy-based sensing strategy.
    Uses information theory to choose the most informative sense squares.
    """
    
    def __init__(self, sense_depth: int = 1, entropy_sample_size: int = 100):
        """
        Initialize Improved TroutBot.
        
        Args:
            sense_depth: How many moves ahead to consider for sensing (1-3)
            entropy_sample_size: Number of possible board states to sample for entropy calculation
        """
        self.board = None
        self.color = None
        self.my_piece_captured_square = None
        self.possible_opponent_pieces = {}  # Track possible piece locations
        self.sense_depth = sense_depth
        self.entropy_sample_size = entropy_sample_size
        self.sense_history = []  # Track past senses to avoid redundancy
        
        self.engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)
    
    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        """Initialize game state."""
        self.board = board
        self.color = color
        self.possible_opponent_pieces = {}
        self.sense_history = []
        print(f"Game started. I am {color}. Opponent: {opponent_name}")
    
    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
        """Track opponent's captures."""
        self.my_piece_captured_square = capture_square
        if captured_my_piece:
            self.board.remove_piece_at(capture_square)
            print(f"Opponent captured my piece at {chess.square_name(capture_square) if capture_square else 'unknown'}")
    
    def calculate_square_entropy(self, square: Square) -> float:
        """
        Calculate Shannon entropy for a square based on possible piece distributions.
        Higher entropy = more uncertainty = potentially more informative to sense.
        
        Entropy formula: H(X) = -Σ p(x) * log2(p(x))
        """
        if not self.possible_opponent_pieces:
            # No prior information - maximum entropy
            return math.log2(13)  # 12 piece types + empty
        
        # Count possible pieces at this square from our belief state
        piece_counts = Counter()
        for board_state in self.possible_opponent_pieces.values():
            if square in board_state:
                piece = board_state[square]
                piece_counts[piece] += 1
        
        if not piece_counts:
            return 0.0  # No uncertainty
        
        total = sum(piece_counts.values())
        entropy = 0.0
        for count in piece_counts.values():
            prob = count / total
            entropy -= prob * math.log2(prob)
        
        return entropy
    
    def calculate_information_gain(self, square: Square, candidate_moves: List[chess.Move]) -> float:
        """
        Calculate expected information gain from sensing a square.
        Considers both immediate piece information and future move implications.
        
        Information Gain = H(current) - H(expected after sense)
        """
        if not self.possible_opponent_pieces:
            return self.calculate_square_entropy(square)
        
        # Simulate possible sense outcomes
        possible_outcomes = {}
        for board_state in self.possible_opponent_pieces.values():
            piece = board_state.get(square)
            outcome_key = piece.symbol() if piece else 'empty'
            possible_outcomes[outcome_key] = possible_outcomes.get(outcome_key, 0) + 1
        
        # Calculate expected entropy after sensing
        total = len(self.possible_opponent_pieces)
        expected_entropy = 0.0
        
        for outcome, count in possible_outcomes.items():
            prob = count / total
            
            # Calculate reduced uncertainty if we get this outcome
            remaining_uncertainty = 0.0
            for other_square in self.get_strategic_squares():
                if other_square != square:
                    remaining_uncertainty += self.calculate_square_entropy(other_square)
            
            expected_entropy += prob * remaining_uncertainty
        
        current_entropy = sum(self.calculate_square_entropy(sq) 
                             for sq in self.get_strategic_squares())
        
        return current_entropy - expected_entropy
    
    def get_strategic_squares(self) -> List[Square]:
        """
        Identify strategically important squares to sense:
        - Center squares (e4, d4, e5, d5)
        - Squares where opponent might develop pieces
        - Squares near our pieces
        - Squares with high entropy
        """
        strategic = []
        
        # Add center squares
        center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
        strategic.extend(center_squares)
        
        # Add squares where opponent might have pieces
        for square, piece in self.board.piece_map().items():
            if piece.color != self.color:  # Opponent piece
                strategic.append(square)
                # Also sense around opponent pieces
                for neighbor in self.get_neighbor_squares(square):
                    strategic.append(neighbor)
        
        # Add squares with high entropy from belief state
        if self.possible_opponent_pieces:
            entropies = [(sq, self.calculate_square_entropy(sq)) 
                        for sq in chess.SQUARES]
            entropies.sort(key=lambda x: x[1], reverse=True)
            strategic.extend([sq for sq, _ in entropies[:10]])
        
        return list(set(strategic))  # Remove duplicates
    
    def get_neighbor_squares(self, square: Square, radius: int = 1) -> List[Square]:
        """Get neighboring squares within given radius."""
        neighbors = []
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        
        for dr in range(-radius, radius + 1):
            for df in range(-radius, radius + 1):
                if dr == 0 and df == 0:
                    continue
                new_rank = rank + dr
                new_file = file + df
                if 0 <= new_rank < 8 and 0 <= new_file < 8:
                    neighbors.append(chess.square(new_file, new_rank))
        
        return neighbors
    
    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        """
        Choose sense square using Shannon entropy strategy.
        Prioritizes squares that maximize information gain.
        """
        # Priority 1: Sense where our piece was just captured
        if self.my_piece_captured_square and self.my_piece_captured_square in sense_actions:
            print(f"Sensing captured square: {chess.square_name(self.my_piece_captured_square)}")
            return self.my_piece_captured_square
        
        # Priority 2: Sense where we might capture next move
        future_move = self.choose_move(move_actions, seconds_left)
        if future_move is not None:
            capture_square = future_move.to_square
            if (self.board.piece_at(capture_square) is not None and 
                capture_square in sense_actions):
                print(f"Sensing potential capture square: {chess.square_name(capture_square)}")
                return capture_square
        
        # Priority 3: Use Shannon entropy for optimal sensing
        # Remove squares with our own pieces (we already know what's there)
        my_squares = {square for square, piece in self.board.piece_map().items() 
                     if piece.color == self.color}
        
        available_senses = [sq for sq in sense_actions if sq not in my_squares]
        
        if not available_senses:
            return random.choice(sense_actions) if sense_actions else None
        
        # Score each available sense square
        scored_senses = []
        for square in available_senses:
            # Skip recently sensed squares to avoid redundancy
            if square in self.sense_history[-5:]:  # Don't repeat recent senses
                continue
            
            # Calculate information gain
            info_gain = self.calculate_information_gain(square, move_actions)
            
            # Bonus for center squares
            if chess.square_rank(square) in [3, 4] and chess.square_file(square) in [3, 4]:
                info_gain *= 1.2
            
            # Bonus for squares near opponent king
            opponent_king = self.board.king(not self.color)
            if opponent_king:
                king_dist = chess.square_distance(square, opponent_king)
                if king_dist <= 2:
                    info_gain *= 1.5
            
            scored_senses.append((info_gain, square))
        
        # Choose square with highest information gain
        if scored_senses:
            scored_senses.sort(key=lambda x: x[0], reverse=True)
            best_square = scored_senses[0][1]
            self.sense_history.append(best_square)
            print(f"Choosing sense square: {chess.square_name(best_square)} "
                  f"(Info Gain: {scored_senses[0][0]:.3f})")
            return best_square
        
        # Fallback: random choice
        return random.choice(available_senses)
    
    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        """Update belief state based on sense results."""
        # Update board with sensed information
        for square, piece in sense_result:
            self.board.set_piece_at(square, piece)
            
            # Update possible opponent piece locations
            if piece and piece.color != self.color:
                if square not in self.possible_opponent_pieces:
                    self.possible_opponent_pieces[square] = {}
                self.possible_opponent_pieces[square][piece.symbol()] = piece
        
        print(f"Sensed {len(sense_result)} squares")
    
    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        """
        Choose best move using enhanced strategy:
        1. Immediate king capture
        2. Stockfish evaluation with position bonuses
        3. Safe move selection
        """
        # Strategy 1: Capture opponent's king if possible
        enemy_king_square = self.board.king(not self.color)
        if enemy_king_square:
            enemy_king_attackers = self.board.attackers(self.color, enemy_king_square)
            if enemy_king_attackers:
                attacker_square = enemy_king_attackers.pop()
                move = chess.Move(attacker_square, enemy_king_square)
                print(f"Capturing king with move: {move}")
                return move
        
        # Strategy 2: Use Stockfish with position evaluation
        try:
            self.board.turn = self.color
            self.board.clear_stack()
            
            # Adjust time based on game phase
            total_moves = len(self.board.move_stack)
            if total_moves < 20:  # Opening
                time_limit = 1.0
            elif total_moves < 40:  # Middlegame
                time_limit = 0.7
            else:  # Endgame
                time_limit = 0.5
            
            result = self.engine.play(self.board, chess.engine.Limit(time=time_limit))
            move = result.move
            
            # Validate move is legal
            if move in move_actions:
                print(f"Stockfish suggests: {move}")
                return move
            
        except chess.engine.EngineTerminatedError:
            print('Stockfish Engine died - restarting...')
            self.restart_engine()
        except chess.engine.EngineError:
            print('Stockfish Engine bad state at "{}"'.format(self.board.fen()))
        
        # Strategy 3: Safe fallback - choose a random safe move
        safe_moves = self.get_safe_moves(move_actions)
        if safe_moves:
            move = random.choice(safe_moves)
            print(f"Fallback safe move: {move}")
            return move
        
        # Strategy 4: Last resort - pass
        print("No safe moves available - passing")
        return None
    
    def get_safe_moves(self, move_actions: List[chess.Move]) -> List[chess.Move]:
        """
        Filter moves to only those that don't hang pieces unnecessarily.
        """
        safe_moves = []
        
        for move in move_actions:
            # Check if move puts our king in check
            temp_board = self.board.copy()
            try:
                temp_board.push(move)
                if temp_board.is_check():  # Don't move into check
                    continue
                
                # Check if the moved piece would be captured immediately
                if temp_board.is_capture(move):
                    # Calculate if it's a good trade
                    captured_piece = self.board.piece_at(move.to_square)
                    moving_piece = self.board.piece_at(move.from_square)
                    
                    if captured_piece and moving_piece:
                        # Prefer capturing higher value pieces
                        if captured_piece.piece_type >= moving_piece.piece_type:
                            safe_moves.append(move)
                    else:
                        safe_moves.append(move)
                else:
                    safe_moves.append(move)
                    
            except Exception:
                continue
        
        return safe_moves if safe_moves else move_actions
    
    def restart_engine(self):
        """Restart Stockfish engine if it crashes."""
        try:
            self.engine.quit()
        except:
            pass
        self.engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)
    
    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        """Update board state after move execution."""
        if taken_move is not None:
            self.board.push(taken_move)
            print(f"Move executed: {taken_move}")
            if captured_opponent_piece:
                print(f"Captured opponent piece at {chess.square_name(capture_square) if capture_square else 'unknown'}")
    
    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        """Clean up resources."""
        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
        
        print(f"Game ended. Winner: {winner_color}, Reason: {win_reason}")
        if winner_color == self.color:
            print("I won! 🎉")
        elif winner_color is not None:
            print("I lost 😢")