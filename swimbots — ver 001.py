import pygame
import pymunk
import pymunk.pygame_util
import math
import random
import copy

# --- KONFIGURACJA ---
WIDTH, HEIGHT = 1000, 600
FPS = 60
POPULATION_SIZE = 10
GENERATION_DURATION = 600  # Ile klatek trwa jedna runda (np. 600 klatek = 10 sekund)
SEGMENTS_PER_BOT = 4

# Zakresy losowania genów (dla pierwszej generacji)
# Geny to: [szybkość, amplituda, przesunięcie_fazy]
GENE_RANGES = [(2.0, 15.0), (0.2, 1.5), (0.0, 1.5)] 

class Swimbot:
    def __init__(self, space, start_pos, genes, color):
        self.space = space
        self.genes = genes  # Lista: [speed, amplitude, phase_shift]
        self.bodies = []
        self.shapes = []
        self.joints = []
        self.color = color
        
        # Budowa ciała
        segment_width = 30
        segment_height = 15
        
        for i in range(SEGMENTS_PER_BOT):
            mass = 0.5  # Zmniejszamy masę z1 do 0.5 (lżejszy bot łatwiej ruszy)
            moment = pymunk.moment_for_box(mass, (segment_width, segment_height))
            body = pymunk.Body(mass, moment)
            body.position = (start_pos[0] - i * (segment_width + 2), start_pos[1])
            
            shape = pymunk.Poly.create_box(body, (segment_width, segment_height))
            shape.elasticity = 0.1
            shape.friction = 0.5
            shape.color = color
            
            # Group=1 oznacza, że wszystkie kształty w tej grupie NIE kolidują ze sobą
            # Dzięki temu boty mogą przez siebie przenikać (wygląda to jak ławica)
            shape.filter = pymunk.ShapeFilter(group=1)
            
            self.space.add(body, shape)
            self.bodies.append(body)
            self.shapes.append(shape)
            
            if i > 0:
                # Pivot joint
                joint = pymunk.PivotJoint(
                    self.bodies[i-1], 
                    self.bodies[i], 
                    (start_pos[0] - i * (segment_width + 2) + (segment_width/2 + 1), start_pos[1])
                )
                # Mięsień (sprężyna)
                spring = pymunk.DampedRotarySpring(
                    self.bodies[i-1], 
                    self.bodies[i], 
                    0,
                    15000, # ZWIĘKSZONO z 3000 na 15000 (silniejsze mięśnie)
                    500    # ZWIĘKSZONO tłumienie stawu dla stabilności do 500
                )
                self.space.add(joint, spring)
                self.joints.append(spring)

    def update(self, time):
        speed, amp, phase = self.genes
        
        for i, spring in enumerate(self.joints):
            # Formuła ruchu oparta na genach
            target_angle = math.sin(time * speed - i * phase) * amp
            spring.rest_angle = target_angle

        # --- NOWA LOGIKA OPORU WODY ---
        for body in self.bodies:
            # Obliczamy kierunek, w którym patrzy segment (jego przód)
            forward = body.rotation_vector
            # Obliczamy prędkość segmentu
            vel = body.velocity
            
            # Wyciągamy prędkość poprzeczną (boczną)
            # To jest klucz: woda stawia opór ruchom bocznym segmentów
            lateral_vel = vel.dot(forward.perpendicular())
            
            # Nakładamy siłę hamującą ruch boczny (tarcie wody)
            # Dzięki temu wygięcie ciała zamienia się w ruch do przodu
            impulse = -forward.perpendicular() * lateral_vel * 0.5  # 3.0 ? Zwiększono siłę odepchnięcia z 0.5
            body.apply_impulse_at_local_point(impulse)

    def get_distance(self):
        # Mierzymy pozycję X "głowy" (pierwszego segmentu)
        return self.bodies[0].position.x

# --- FUNKCJE EWOLUCYJNE ---

def create_random_genes():
    return [random.uniform(r[0], r[1]) for r in GENE_RANGES]

def mutate(genes):
    new_genes = []
    mutation_rate = 0.1 # 10% szans na dużą zmianę, 100% na małą zmianę
    
    for val in genes:
        # Mała zmiana (dryf genetyczny)
        val += random.uniform(-0.1, 0.1)
        
        # Rzadka duża mutacja
        if random.random() < mutation_rate:
            val += random.uniform(-0.5, 0.5)
            
        new_genes.append(val)
    
    # Zabezpieczenie przed wartościami ujemnymi dla amplitudy/szybkości, jeśli chcemy
    # (choć ujemna szybkość to po prostu ruch w drugą stronę fazy, co też jest ok)
    return new_genes

def setup_simulation(genes_list=None):
    space = pymunk.Space()
    space.damping = 0.9  # 0.9 to lekki opór, który pozwala na zachowanie pędu
    
    bots = []
    start_x = 100
    start_y = HEIGHT // 2
    
    for i in range(POPULATION_SIZE):
        # Jeśli nie mamy genów (pierwsza runda), losujemy
        if genes_list is None:
            genes = create_random_genes()
        else:
            genes = genes_list[i]
            
        # Losowy kolor dla każdego bota, żeby było ładnie
        # Ale liderzy z poprzedniej rundy będą zieloni w wizualizacji (opcjonalne)
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255), 255)
        
        # Lekki rozrzut w pionie, żeby nie startowały idealnie w jednym punkcie (estetyka)
        pos = (start_x, start_y + random.randint(-50, 50))
        
        bot = Swimbot(space, pos, genes, color)
        bots.append(bot)
        
    return space, bots

# --- GŁÓWNA PĘTLA ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    draw_options = pymunk.pygame_util.DrawOptions(screen)
    font = pygame.font.SysFont("Arial", 18)

    generation_count = 1
    current_genes = None # Na początku brak
    
    # Start symulacji
    space, bots = setup_simulation()
    
    frame_count = 0
    time_sim = 0
    running = True
    
    max_distance_record = 0
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 1. Fizyka i logika
        time_sim += 1/FPS
        for bot in bots:
            bot.update(time_sim)
        
        space.step(1/FPS)
        frame_count += 1

        # 2. Sprawdzenie końca generacji
        if frame_count >= GENERATION_DURATION:
            # --- EWOLUCJA ---
            
            # Sortujemy boty wg dystansu (malejąco)
            bots.sort(key=lambda b: b.get_distance(), reverse=True)
            
            best_bot = bots[0]
            record_now = best_bot.get_distance()
            if record_now > max_distance_record:
                max_distance_record = record_now
                
            print(f"Gen {generation_count} zakończona. Najlepszy dystans: {record_now:.2f}")
            print(f"Najlepsze geny: {['%.2f' % g for g in best_bot.genes]}")
            
            # Wybieramy rodziców (np. top 25% populacji)
            top_performers = bots[:POPULATION_SIZE // 4]
            
            next_generation_genes = []
            
            # Elityzm: Najlepszy z poprzedniej rundy przechodzi bez zmian (król)
            next_generation_genes.append(top_performers[0].genes)
            
            # Reszta to dzieci najlepszych
            while len(next_generation_genes) < POPULATION_SIZE:
                parent = random.choice(top_performers)
                child_genes = mutate(parent.genes)
                next_generation_genes.append(child_genes)
            
            # Reset
            current_genes = next_generation_genes
            space, bots = setup_simulation(current_genes)
            frame_count = 0
            time_sim = 0
            generation_count += 1

        # 3. Rysowanie
        screen.fill((20, 20, 30))
        
        # Rysujemy linię startu
        pygame.draw.line(screen, (255, 255, 255), (100, 0), (100, HEIGHT), 1)
        
        space.debug_draw(draw_options)
        
        # Interfejs
        info_text = [
            f"Pokolenie: {generation_count}",
            f"Czas do końca rundy: {(GENERATION_DURATION - frame_count)//60}s",
            f"Najlepszy w historii: {int(max_distance_record)}"
        ]
        
        for i, line in enumerate(info_text):
            text_surf = font.render(line, True, (200, 200, 200))
            screen.blit(text_surf, (10, 10 + i * 20))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
