"""Scheduler Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from flask import request, jsonify, current_app
from core.logger import get_logger
from core.db.ups import db
from datetime import datetime
from .scheduler import scheduler, calculate_report_period
from .periods import parse_schedule_range_dates, resolve_schedule_timezone
import time
import hashlib
import pytz
from core.multi_nut.target_scope import apply_target_scope, resolve_settings_target_id

# Configure logging
scheduler_logger = get_logger('scheduler')

# Global timestamp tracking
_last_schedule_save_time = 0
_schedule_save_cooldown = 2  # seconds

# Global timestamp tracking for test schedule
_last_test_schedule_time = 0
_test_schedule_cooldown = 0.5  # seconds - reduced from 2 seconds to be less restrictive
_last_test_request_hash = None
_last_test_request_time = 0

# Track when all schedules have been deleted to reuse IDs
_all_schedules_deleted = False


def _resolve_scope_target_id() -> int | None:
    requested_target_id = request.args.get('target_id', type=int)
    return resolve_settings_target_id(requested_target_id)


def _scoped_query(model_class, target_id):
    return apply_target_scope(model_class, model_class.query, target_id)


def _global_mail_query(mail_model):
    query = mail_model.query
    if hasattr(mail_model, 'target_id'):
        query = query.filter(mail_model.target_id.is_(None))
    return query

# Helper function to safely get the MailConfig model
def get_mail_config_model():
    """Safely get the MailConfig model from db.ModelClasses"""
    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'MailConfig'):
        return db.ModelClasses.MailConfig
    scheduler_logger.error("❌ MailConfig model not available through db.ModelClasses")
    return None

def register_scheduler_routes(app):
    """Register all scheduler-related routes"""
    
    @app.route('/api/settings/report/schedules', methods=['GET', 'POST'])
    @app.route('/api/settings/report/schedules/<int:schedule_id>', methods=['GET', 'PUT', 'DELETE'])
    def handle_report_schedules(schedule_id=None):
        """Handle report schedules operations"""
        global _last_schedule_save_time, _all_schedules_deleted
        
        try:
            scheduler_logger.info(f"📅 Handling report schedules request: {request.method}")
            
            # Get the ReportSchedule model from db.ModelClasses
            ReportScheduleModel = None
            if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'ReportSchedule'):
                ReportScheduleModel = db.ModelClasses.ReportSchedule
            
            if ReportScheduleModel is None:
                scheduler_logger.error("❌ ReportSchedule model not available")
                return jsonify({
                    'success': False,
                    'message': 'Report schedule functionality not available'
                }), 500

            scoped_target_id = _resolve_scope_target_id()
            scoped_schedule_query = _scoped_query(ReportScheduleModel, scoped_target_id)
            
            if request.method == 'POST':
                # Debounce protection - prevent duplicate form submissions
                current_time = time.time()
                if current_time - _last_schedule_save_time < _schedule_save_cooldown:
                    scheduler_logger.warning(f"Schedule save called too soon after previous call ({current_time - _last_schedule_save_time:.2f}s < {_schedule_save_cooldown}s)")
                    return jsonify({
                        'success': False,
                        'message': 'Please wait before submitting again'
                    }), 429
                
                _last_schedule_save_time = current_time
                
                # Debug logging for sequence state
                scheduler_logger.debug(f"🔍 DEBUG - All schedules deleted flag: {_all_schedules_deleted}")
                
                data = request.get_json()
                scheduler_logger.info(f"📤 Creating new schedule with data: {data}")
                
                # Validate fields
                if not all(k in data for k in ['reports', 'period_type']):
                    return jsonify({
                        'success': False,
                        'message': 'Missing required fields'
                    }), 400
                    
                # Validate mail_config_id
                if 'mail_config_id' not in data or not data['mail_config_id']:
                    return jsonify({
                        'success': False,
                        'message': 'mail_config_id is required'
                    }), 400
                    
                # Verify mail_config_id exists in the database
                try:
                    MailConfig = get_mail_config_model()
                    if MailConfig:
                        mail_query = _global_mail_query(MailConfig)
                        mail_config = mail_query.filter(MailConfig.id == int(data['mail_config_id'])).first()
                        if not mail_config:
                            return jsonify({
                                'success': False,
                                'message': f"Mail configuration with ID {data['mail_config_id']} not found"
                            }), 400
                except Exception as e:
                    scheduler_logger.error(f"Error validating mail_config_id: {str(e)}")
                    return jsonify({
                        'success': False,
                        'message': 'Error validating mail configuration'
                    }), 500

                # If period_type is 'range', verify that from_date and to_date are present
                if data.get('period_type') == 'range' and (not data.get('from_date') or not data.get('to_date')):
                    return jsonify({
                        'success': False,
                        'message': 'From and To dates required for range period'
                    }), 400

                # If time is empty, use a default value
                time_str = data.get('time', '00:00')
                if not time_str:
                    time_str = '00:00'

                # Convert the time string from target timezone to UTC for storage
                try:
                    # Parse hour and minute
                    hour, minute = map(int, time_str.split(':'))
                    
                    app_tz = resolve_schedule_timezone(
                        target_id=scoped_target_id,
                        fallback_tz=current_app.CACHE_TIMEZONE,
                    )
                    
                    # Create datetime in app timezone (user's input timezone)
                    now = datetime.now()
                    naive_time = datetime(now.year, now.month, now.day, hour, minute, 0)
                    app_time = app_tz.localize(naive_time)
                    
                    # Convert to UTC for storage
                    utc_time = app_time.astimezone(pytz.UTC)
                    
                    # Format as time string for database storage
                    time_str = f"{utc_time.hour:02d}:{utc_time.minute:02d}"
                    scheduler_logger.info(
                        f"🕒 Converted time from target timezone {hour:02d}:{minute:02d} to UTC {time_str} for database storage"
                    )
                    
                    # Split for cron expression
                    hour, minute = time_str.split(':')
                except Exception as e:
                    scheduler_logger.error(f"⚠️ Error converting time to UTC: {str(e)}. Using original time.")
                    # Split time in safety if conversion fails
                    hour, minute = time_str.split(':')
                
                # Convert to cron expression
                days_str = ','.join(str(d) for d in data.get('days', [])) or '*'
                cron_expr = f"{minute} {hour} * * {days_str}"

                # Process reports to ensure no duplicates when creating a new schedule
                if 'reports' in data:
                    if isinstance(data['reports'], list):
                        # Get unique values preserving order
                        seen = set()
                        unique_reports = [x for x in data['reports'] if x and not (x in seen or seen.add(x))]
                        reports = ','.join(unique_reports)
                    else:
                        # Handle string input
                        if data['reports']:
                            items = data['reports'].split(',')
                            seen = set()
                            unique_reports = [x for x in items if x and not (x in seen or seen.add(x))]
                            reports = ','.join(unique_reports)
                        else:
                            reports = ''
                else:
                    reports = ''
                    
                # Create new schedule in the database
                new_schedule = ReportScheduleModel(
                    time=time_str,
                    days=days_str,
                    reports=reports,
                    email=data.get('email'),
                    mail_config_id=data.get('mail_config_id'),
                    period_type=data['period_type'],
                    enabled=data.get('enabled', True)
                )
                if hasattr(new_schedule, 'target_id'):
                    new_schedule.target_id = scoped_target_id
                
                # If period_type is 'range', save also from_date and to_date
                if data.get('period_type') == 'range':
                    try:
                        from_date, to_date = parse_schedule_range_dates(
                            data.get('from_date'),
                            data.get('to_date'),
                            target_id=scoped_target_id,
                            fallback_tz=current_app.CACHE_TIMEZONE,
                        )
                        new_schedule.from_date = from_date
                        new_schedule.to_date = to_date
                    except Exception as e:
                        scheduler_logger.error(f"Error parsing dates for range: {e}")
                        return jsonify({
                            'success': False,
                            'message': f'Invalid date format: {str(e)}'
                        }), 400
                
                # If all schedules were deleted and we're creating a new one,
                # try to find the lowest available ID
                if _all_schedules_deleted:
                    scheduler_logger.info("🔄 All schedules were previously deleted - trying to reset sequence")
                    try:
                        # Get all existing IDs
                        existing_ids = scoped_schedule_query.with_entities(ReportScheduleModel.id).all()
                        existing_ids = [item[0] for item in existing_ids]
                        
                        # If no schedules exist, start with ID 1
                        if not existing_ids:
                            scheduler_logger.info("🔍 No existing schedules found - attempting to reset sequence to 0")
                            
                            # First check if the sqlite_sequence table exists
                            result = db.session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone()
                            
                            if result:
                                # Check if our table is in the sequence table
                                sequence_result = db.session.execute(
                                    "SELECT seq FROM sqlite_sequence WHERE name = 'ups_report_schedules'"
                                ).fetchone()
                                
                                if sequence_result:
                                    current_seq = sequence_result[0]
                                    scheduler_logger.info(f"🔍 Current sequence value for ups_report_schedules: {current_seq}")
                                    
                                    # Reset the sequence
                                    db.session.execute(
                                        "UPDATE sqlite_sequence SET seq = 0 WHERE name = 'ups_report_schedules'"
                                    )
                                    db.session.commit()
                                    scheduler_logger.info("✅ Successfully reset sequence to 0")
                                else:
                                    scheduler_logger.info("ℹ️ Table ups_report_schedules not found in sqlite_sequence")
                            else:
                                scheduler_logger.info("ℹ️ sqlite_sequence table not found - auto-increment will start from 1")
                    except Exception as e:
                        scheduler_logger.warning(f"⚠️ Could not reset sequence counter: {str(e)}")
                        scheduler_logger.debug(f"🔍 DEBUG - Sequence reset exception details: {e.__class__.__name__}")
                
                # Reset the flag since we're creating a new schedule
                _all_schedules_deleted = False
                
                db.session.add(new_schedule)
                db.session.commit()
                scheduler.last_schedule_id = new_schedule.id  # Store the ID
                
                # Add the job using the schedule library
                success = scheduler._add_job_from_schedule(new_schedule)
                
                if success:
                    scheduler_logger.info(f"✅ Schedule created successfully with ID: {new_schedule.id}")
                    return jsonify({
                        'success': True,
                        'data': {
                            'id': scheduler.last_schedule_id,  # Add the schedule ID
                            'message': 'Schedule saved successfully'
                        }
                    })
                else:
                    scheduler_logger.error("❌ Failed to create schedule")
                    db.session.delete(new_schedule)
                    db.session.commit()
                    return jsonify({
                        'success': False,
                        'message': 'Failed to add job to scheduler'
                    }), 500

            elif request.method == 'GET':
                if schedule_id is not None:
                    # Handle individual schedule retrieval
                    schedule = scoped_schedule_query.filter(ReportScheduleModel.id == int(schedule_id)).first()
                    if not schedule:
                        return jsonify({
                            'success': False,
                            'message': 'Schedule not found'
                        }), 404
                    
                    return jsonify({
                        'success': True,
                        'data': schedule.to_dict()
                    })
                else:
                    # Handle list of all schedules
                    schedules = scoped_schedule_query.order_by(ReportScheduleModel.id.asc()).all()
                    return jsonify({
                        'success': True,
                        'data': [schedule.to_dict() for schedule in schedules]
                    })

            elif request.method == 'PUT':
                schedule = scoped_schedule_query.filter(ReportScheduleModel.id == int(schedule_id)).first()
                if not schedule:
                    return jsonify({
                        'success': False,
                        'message': 'Schedule not found'
                    }), 404

                data = request.get_json()
                scheduler_logger.info(f"📝 Updating schedule {schedule_id} with data: {data}")
                scheduler_logger.info(f"📋 REPORTS field present: {'reports' in data}")

                # Convert time to UTC if present in the update data
                if 'time' in data and data['time']:
                    try:
                        # Parse hour and minute
                        hour, minute = map(int, data['time'].split(':'))
                        schedule_target_id = getattr(schedule, 'target_id', scoped_target_id)
                        
                        # Resolve schedule timezone (target-specific when available)
                        app_tz = resolve_schedule_timezone(
                            target_id=schedule_target_id,
                            fallback_tz=current_app.CACHE_TIMEZONE,
                        )
                        
                        # Create datetime in app timezone (user's input timezone)
                        now = datetime.now()
                        naive_time = datetime(now.year, now.month, now.day, hour, minute, 0)
                        app_time = app_tz.localize(naive_time)
                        
                        # Convert to UTC for storage
                        utc_time = app_time.astimezone(pytz.UTC)
                        
                        # Format as time string for database storage
                        data['time'] = f"{utc_time.hour:02d}:{utc_time.minute:02d}"
                        scheduler_logger.info(
                            f"🕒 Update: Converted time from target timezone {hour:02d}:{minute:02d} to UTC {data['time']} for database storage"
                        )
                    except Exception as e:
                        scheduler_logger.error(f"⚠️ Error converting update time to UTC: {str(e)}. Using original time.")

                if 'reports' in data:
                    scheduler_logger.info(f"📋 REPORTS value: {data['reports']}, type: {type(data['reports'])}")

                # Update schedule fields
                if 'time' in data:
                    schedule.time = data['time']
                if 'days' in data:
                    schedule.days = ','.join(map(str, data['days']))
                if 'reports' in data:
                    # Get clean reports list without duplicates
                    if isinstance(data['reports'], list):
                        # Get unique values preserving order
                        seen = set()
                        unique_reports = [x for x in data['reports'] if x and not (x in seen or seen.add(x))]
                        schedule.reports = ','.join(unique_reports)
                    else:
                        # Handle string input by splitting, deduplicating, and rejoining
                        if data['reports']:
                            items = data['reports'].split(',')
                            seen = set()
                            unique_reports = [x for x in items if x and not (x in seen or seen.add(x))]
                            schedule.reports = ','.join(unique_reports)
                        else:
                            schedule.reports = ''
                        
                    scheduler_logger.info(f"Updated reports for schedule {schedule_id}: {schedule.reports}")
                if 'email' in data:
                    schedule.email = data['email']
                if 'mail_config_id' in data:
                    # Validate mail_config_id if it's being updated
                    if not data['mail_config_id']:
                        return jsonify({
                            'success': False,
                            'message': 'mail_config_id cannot be empty'
                        }), 400
                        
                    # Verify mail_config_id exists in the database
                    try:
                        MailConfig = get_mail_config_model()
                        if MailConfig:
                            mail_query = _global_mail_query(MailConfig)
                            mail_config = mail_query.filter(MailConfig.id == int(data['mail_config_id'])).first()
                            if not mail_config:
                                return jsonify({
                                    'success': False,
                                    'message': f"Mail configuration with ID {data['mail_config_id']} not found"
                                }), 400
                    except Exception as e:
                        scheduler_logger.error(f"Error validating mail_config_id: {str(e)}")
                        return jsonify({
                            'success': False,
                            'message': 'Error validating mail configuration'
                        }), 500
                        
                    schedule.mail_config_id = data['mail_config_id']
                if 'period_type' in data:
                    schedule.period_type = data['period_type']
                    # If period_type is 'range', update also from_date and to_date
                    if data['period_type'] == 'range':
                        if 'from_date' in data and 'to_date' in data:
                            try:
                                schedule_target_id = getattr(schedule, 'target_id', scoped_target_id)
                                from_date, to_date = parse_schedule_range_dates(
                                    data['from_date'],
                                    data['to_date'],
                                    target_id=schedule_target_id,
                                    fallback_tz=current_app.CACHE_TIMEZONE,
                                )
                                schedule.from_date = from_date
                                schedule.to_date = to_date
                            except Exception as e:
                                scheduler_logger.error(f"Error parsing dates for range update: {e}")
                                return jsonify({
                                    'success': False,
                                    'message': f'Invalid date format: {str(e)}'
                                }), 400
                        else:
                            return jsonify({
                                'success': False,
                                'message': 'Both from_date and to_date are required for range period type'
                            }), 400
                if 'enabled' in data:
                    schedule.enabled = data['enabled']
                
                scheduler_logger.info(f"💾 Committing changes to schedule {schedule_id}")
                db.session.commit()
                
                # Update scheduler job
                scheduler_logger.info(f"🔄 Updating scheduler job for schedule {schedule_id}")
                scheduler.clear_jobs_for_schedule(schedule.id)
                success = scheduler._add_job_from_schedule(schedule)
                
                if not success:
                    scheduler_logger.error(f"❌ Failed to update schedule {schedule_id} in scheduler")
                    return jsonify({
                        'success': False,
                        'message': 'Failed to update schedule in scheduler'
                    }), 500

                scheduler_logger.info(f"✅ Schedule {schedule_id} updated successfully")
                return jsonify({
                    'success': True,
                    'data': schedule.to_dict()
                })

            elif request.method == 'DELETE':
                schedule = scoped_schedule_query.filter(ReportScheduleModel.id == int(schedule_id)).first()
                if not schedule:
                    return jsonify({
                        'success': False,
                        'message': 'Schedule not found'
                    }), 404

                # Log the current schedule being deleted
                scheduler_logger.info(f"🔍 DEBUG - Deleting schedule with ID: {schedule_id}")
                
                # Remove from scheduler
                scheduler_logger.info(f"🗑️ Removing scheduler job for schedule {schedule_id}")
                scheduler.clear_jobs_for_schedule(schedule.id)
                
                # Remove from database
                scheduler_logger.info(f"🗑️ Removing schedule {schedule_id} from database")
                db.session.delete(schedule)
                db.session.commit()
                
                # Check if this was the last schedule
                remaining_count = scoped_schedule_query.count()
                scheduler_logger.info(f"ℹ️ {remaining_count} schedules remaining after deletion")
                
                # If no schedules remain, set the flag to true
                if remaining_count == 0:
                    _all_schedules_deleted = True
                    scheduler_logger.info("🔄 All schedules have been deleted, will reuse IDs for new schedules")
                    
                    # Log sequence information if possible
                    try:
                        # Check if sqlite_sequence table exists
                        result = db.session.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
                        ).fetchone()
                        
                        if result:
                            # Check current sequence value
                            seq_value = db.session.execute(
                                "SELECT seq FROM sqlite_sequence WHERE name='ups_report_schedules'"
                            ).fetchone()
                            
                            if seq_value:
                                scheduler_logger.info(f"🔍 DEBUG - Current sequence value for ups_report_schedules: {seq_value[0]}")
                            else:
                                scheduler_logger.info("🔍 DEBUG - ups_report_schedules not found in sqlite_sequence")
                        else:
                            scheduler_logger.info("🔍 DEBUG - sqlite_sequence table not found")
                    except Exception as e:
                        scheduler_logger.debug(f"🔍 DEBUG - Could not check sequence information: {str(e)}")
                
                scheduler_logger.info(f"✅ Schedule {schedule_id} deleted successfully")
                return jsonify({
                    'success': True,
                    'message': 'Schedule deleted successfully'
                })
                
        except Exception as e:
            scheduler_logger.error(f"❌ Error handling report schedules: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    @app.route('/api/settings/report/schedules/test', methods=['POST'])
    def test_schedule():
        """Test schedule configuration"""
        global _last_test_schedule_time, _last_test_request_hash, _last_test_request_time
        
        try:
            # Stronger debounce protection with unique identifier
            current_time = time.time()
            request_json = request.get_json()
            
            # Generate a request identifier based on content
            request_hash = hashlib.md5(str(request_json).encode()).hexdigest()
            
            # Check if this exact request was processed recently (5 seconds)
            if _last_test_request_hash == request_hash and current_time - _last_test_request_time < 5:
                scheduler_logger.warning(f"Identical test request detected within 5 seconds. Preventing duplicate.")
                return jsonify({
                    'success': True,
                    'message': 'Request already processed. Please wait a moment before trying again.'
                })
                
            # Standard rate limiting
            if current_time - _last_test_schedule_time < _test_schedule_cooldown:
                scheduler_logger.warning(f"Test schedule called too soon after previous call ({current_time - _last_test_schedule_time:.2f}s < {_test_schedule_cooldown}s)")
                return jsonify({
                    'success': False,
                    'message': 'Please wait before submitting again'
                }), 429
            
            # Update rate limit trackers
            _last_test_schedule_time = current_time
            _last_test_request_hash = request_hash
            _last_test_request_time = current_time
            
            data = request_json
            scheduler_logger.info(f"🧪 Testing schedule with data: {data}")
            scoped_target_id = _resolve_scope_target_id()
            
            # Validate required fields
            if 'reports' not in data or not data['reports']:
                return jsonify({
                    'success': False,
                    'message': 'No report types specified'
                }), 400
            
            # Validate report types
            if not isinstance(data['reports'], list):
                return jsonify({
                    'success': False,
                    'message': 'Reports must be a list'
                }), 400
            
            # Validate the email configuration
            mail_config_id = data.get('mail_config_id')
            if not mail_config_id:
                return jsonify({
                    'success': False,
                    'message': 'mail_config_id is required'
                }), 400
            
            # Verify mail_config_id exists
            MailConfig = get_mail_config_model()
            if not MailConfig:
                return jsonify({
                    'success': False,
                    'message': 'Mail configuration not available'
                }), 500
            
            mail_query = _global_mail_query(MailConfig)
            mail_config = mail_query.filter(MailConfig.id == int(mail_config_id)).first()
            if not mail_config:
                return jsonify({
                    'success': False,
                    'message': f'Mail configuration with ID {mail_config_id} not found'
                }), 404
            
            period_type = data.get('period_type', 'yesterday')
            
            if period_type == 'range':
                from_date_str = data.get('from_date')
                to_date_str = data.get('to_date')
                
                if not from_date_str or not to_date_str:
                    return jsonify({
                        'success': False,
                        'message': 'From and To dates required for range'
                    }), 400
                    
                # Convert strings to datetime objects with timezone
                try:
                    start_date, end_date = parse_schedule_range_dates(
                        from_date_str,
                        to_date_str,
                        target_id=scoped_target_id,
                        fallback_tz=current_app.CACHE_TIMEZONE,
                    )
                except ValueError as e:
                    scheduler_logger.error(f"❌ Error parsing dates: {str(e)}")
                    return jsonify({
                        'success': False,
                        'message': f'Invalid date format: {str(e)}'
                    }), 400
            else:
                # Use calculate_report_period function
                start_date, end_date = calculate_report_period(
                    period_type,
                    target_id=scoped_target_id,
                )
                
                # Ensure dates have timezone
                tz = resolve_schedule_timezone(
                    target_id=scoped_target_id,
                    fallback_tz=current_app.CACHE_TIMEZONE,
                )
                if start_date and start_date.tzinfo is None:
                    start_date = tz.localize(start_date)
                if end_date and end_date.tzinfo is None:
                    end_date = tz.localize(end_date)
            
            scheduler_logger.info(f"📧 Sending test report from {start_date} to {end_date}")
            
            # Use report_manager to generate and send report
            success = scheduler.report_manager.generate_and_send_report(
                report_types=data['reports'],
                email=None,  # We're using mail_config_id instead
                from_date=start_date,
                to_date=end_date,
                period_type=period_type,
                id_email=mail_config_id,
                target_id=scoped_target_id,
                scheduled=False
            )
            
            if success:
                scheduler_logger.info("✅ Test report sent successfully")
                return jsonify({
                    'success': True,
                    'message': 'Test report sent successfully',
                    'details': {
                        'mail_config_id': mail_config_id,
                        'from_date': start_date.isoformat(),
                        'to_date': end_date.isoformat(),
                        'reports': data['reports'],
                        'period_type': period_type
                    }
                })
            else:
                scheduler_logger.error("❌ Failed to send test report")
                return jsonify({
                    'success': False,
                    'message': 'Failed to send test report'
                }), 500
                
        except Exception as e:
            scheduler_logger.error(f"❌ Error testing schedule: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    @app.route('/api/settings/report/disable', methods=['POST'])
    def disable_report_scheduler():
        """Disable all report schedules"""
        try:
            # Get the ReportSchedule model from db.ModelClasses
            ReportScheduleModel = None
            if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'ReportSchedule'):
                ReportScheduleModel = db.ModelClasses.ReportSchedule
            else:
                return jsonify(success=False, message="Report schedule functionality not available"), 500

            scoped_target_id = _resolve_scope_target_id()
            scoped_schedule_query = _scoped_query(ReportScheduleModel, scoped_target_id)
            scoped_schedule_query.update({ReportScheduleModel.enabled: False})
            db.session.commit()
            return jsonify(success=True, message="Report scheduler disabled successfully.")
        except Exception as e:
            db.session.rollback()
            return jsonify(success=False, message=str(e)), 500
            
    return app 
