# huey_worker.py
import sys
from huey.consumer import Consumer
from huey_config import huey

def main():
    """
    Запускает Huey consumer для обработки задач из очереди.
    """
    # Создаем consumer
    consumer = Consumer(huey)
    
    print(f"Huey consumer started")
    
    try:
        # Запускаем consumer
        consumer.run()
    except KeyboardInterrupt:
        print("Consumer stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Consumer shutdown complete")

if __name__ == '__main__':
    main()