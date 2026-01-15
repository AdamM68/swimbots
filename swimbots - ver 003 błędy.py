# ver 003 
import pygame
import pymunk
import pymunk.pygame_util
import math
import random

# --- KONFIGURACJA ---
WIDTH, HEIGHT = 1000, 600
FPS = 60
POPULATION_SIZE = 12
GENERATION_DURATION = 600  # 10 sekund na rundę
SEGMENTS_PER_BOT = 4

# Zakresy genów: [szybkość machania, amplituda wygięcia, przesunięcie fazy fali]
GENE_RANGES = [(2.0, 12.0), (0.2, 1.2), (0.3, 1.5)] 

class Swimbot:
    def __init__(self, space, start_pos, genes, color):
        self.space = space
        self.genes = genes  # [speed, amplitude, phase_shift]
        self.bodies = []
        self.shapes = []
        self.joints = []
        self.color = color
        
        segment_width = 30
        segment_height = 12
        
        for i in range(SEGMENTS_PER_BOT):
            mass = 0.5
            moment = pymunk.moment_for_box(mass, (segment_width, segment_height))
            body = pymunk.Body(mass, moment)
            body.position = (start_pos[0] - i * (segment_width + 2), start_pos[1])
            
            # STABILIZACJA: Limity prędkości zapobiegają "wystrzeliwaniu" bota w kosmos
            body.velocity_limit = 400
            body.angular_velocity_limit = 10
            
            shape = pymunk.Poly.create_box(body, (segment_width, segment_height))
            shape.color = color
            shape.filter = pymunk.ShapeFilter(group=1) # Brak kolizji między botami
            
            self.space.add(body, shape)
            self.bodies.append(body)
            self.shapes.append(shape)
            
            if i > 0:
                # Połączenie segmentów
                joint = pymunk.PivotJoint(
                    self.bodies[i-1], self.bodies[i], 
                    (body.position.x + segment_width/2 + 1, body.position.y)
                )
                # Mięśnie (silne sprężyny)
                spring = pymunk.DampedRotarySpring(
                    self.bodies[i-1], self.bodies[i], 0, 20000, 800
                )
                self.space.add(joint, spring)
                self.joints.append(spring)

    def update(self, time):
        speed, amp, phase = self.genes
        
        # Ruch falowy mięśni
        for i, spring in enumerate(self.joints):
            target_angle = math.sin(time * speed - i * phase) * amp
            spring.rest_angle = target_angle

        # FIZYKA PŁYWANIA: Opór poprzeczny (zamiana machania na ruch do przodu)
        for body in self.bodies:
            forward = body.rotation_vector
            vel = body.velocity
            lateral_vel = vel.dot(forward.perpendicular())
            
            # Siła odśrodkowa wody
            impulse = -forward.perpendicular() * lateral_vel * 2.0
            body.apply_impulse_at_local_point(impulse)

    def get_distance(self):
        # Pobieramy pozycję X głowy. Jeśli bot "wybuchł", zwracamy 0.
        pos_x = self.bodies[0].position.x
        if math.isnan(pos_x) or math.isinf(pos_x):
            return 0
        return pos_x

# --- FUNKCJE EWOLUCYJNE ---

def create_random_genes():
    return [random.uniform(r[0], r[1]) for r in GENE_RANGES]

def mutate(genes):
    new_genes = []
    for i, val in enumerate(genes):
        # Mała zmiana
        val += random.uniform(-0.15, 0.15)
        # Pilnowanie zakresów (zabezpieczenie przed ekstremami)
        low, high = GENE_RANGES[i]
        val = max(low, min(val, high))
        new_genes.append(val)
    return new_genes

def setup_simulation(genes_list=None):
    space = pymunk.Space()
    space.damping = 0.8  # Stabilny opór otoczenia
    
    bots = []
    for i in range(POPULATION_SIZE):
        genes = genes_list[i] if genes_list else create_random_genes()
        color = (random.randint(70, 255), random.randint(70, 255), random.randint(70, 255), 255)
        pos = (120, random.randint(100, HEIGHT - 100))
        bots.append(Swimbot(space, pos, genes, color))
        
    return space, bots

# --- GŁÓWNA PĘTLA ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Gene Pool Mini - Symulacja Ewolucyjna")
    clock = pygame.time.Clock()
    draw_options = pymunk.pygame_util.DrawOptions(screen)
    font = pygame.font.SysFont("Consolas", 16)

    generation = 1
    space, bots = setup_simulation()
    
    frame_count = 0
    time_sim = 0
    max_dist_all_time = 0
    running = True
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Aktualizacja fizyki
        time_sim += 1/FPS
        for bot in bots:
            bot.update(time_sim)
        
        space.step(1/FPS)
        frame_count += 1

        # Koniec pokolenia
        if frame_count >= GENERATION_DURATION:
            # Sortowanie botów (odfiltrowanie błędnych wyników)
            bots = [b for b in bots if b.get_distance() < WIDTH * 2] # Ignoruj teleporty
            bots.sort(key=lambda b: b.get_distance(), reverse=True)
            
            best_bot = bots[0]
            dist = best_bot.get_distance()
            max_dist_all_time = max(max_dist_all_time, dist)
            
            print(f"Pokolenie {generation} | Najlepszy wynik: {int(dist)}")
            
            # Selekcja (Top 3 rodziców)
            parents = bots[:3]
            next_genes = [p.genes for p in parents] # Elityzm (rodzice przechodzą dalej)
            
            while len(next_genes) < POPULATION_SIZE:
                parent = random.choice(parents)
                next_genes.append(mutate(parent.genes))
            
            space, bots = setup_simulation(next_genes)
            frame_count = 0
            time_sim = 0
            generation += 1

        # Rysowanie
        screen.fill((10, 15, 25))
        pygame.draw.line(screen, (50, 50, 80), (120, 0), (120, HEIGHT), 2) # Start
        
        space.debug_draw(draw_options)
        
        # Interfejs
        overlay = [
            f"Pokolenie: {generation}",
            f"Czas rundy: {(GENERATION_DURATION - frame_count)//60}s",
            f"Rekord dystansu: {int(max_dist_all_time)}"
        ]
        for i, text in enumerate(overlay):
            screen.blit(font.render(text, True, (255, 255, 255)), (15, 15 + i*20))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
